"""Synthetic-only consistency and corruption tests; no provider access."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from evaluation.audit_pilot import audit
from experiments.plan_pilot import pilot_plan
from experiments.run_pilot import run_pilot


class FakeProvider:
    def __init__(self):
        self.calls = 0
        self.chat = SimpleNamespace(completions=self)

    def create(self, **request):
        self.calls += 1
        if len(request['messages']) == 1:
            text = 'SYNTHETIC AUDIT FIXTURE: the user wants to answer email.'
        elif 'priority of Task A is 9' in request['messages'][-1]['content']:
            text = '{"decision":"choose","task":"A"}'
        else:
            text = '{"decision":"defer","task":null}'
        return SimpleNamespace(model=request['model'], _request_id=f'fake-only-{self.calls}',
                               system_fingerprint='SYNTHETIC_TEST_ONLY',
                               usage=SimpleNamespace(prompt_tokens=100, completion_tokens=10, total_tokens=110),
                               choices=[SimpleNamespace(finish_reason='stop',
                                                        message=SimpleNamespace(content=text, refusal=None))])


class AuditTests(unittest.TestCase):
    def setUp(self):
        for target in ('socket.socket.connect', 'socket.socket.connect_ex', 'socket.create_connection'):
            blocker = patch(target, side_effect=AssertionError('Network forbidden in audit tests'))
            blocker.start()
            self.addCleanup(blocker.stop)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.run = self.root / 'synthetic'
        self.plan = pilot_plan()
        self.fake = FakeProvider()
        run_pilot(self.run, mode='live', plan=self.plan, approved_hash=self.plan['plan_sha256'],
                  provider=self.fake)

    def test_complete_fixture_and_raw_preservation(self):
        before = {p.name:p.read_bytes() for p in self.run.iterdir()}
        result = audit(self.run, self.plan['plan_sha256'])
        self.assertEqual(result['trials'], 40)
        self.assertEqual(result['provider_calls'], 80)
        self.assertEqual(result['unique_request_ids'], 80)
        self.assertEqual(result['token_totals']['prompt_tokens'], 8000)
        self.assertEqual(before, {p.name:p.read_bytes() for p in self.run.iterdir()})
        self.assertEqual(self.fake.calls, 80)

    def test_wrong_plan_and_partial_journal_rejected(self):
        with self.assertRaises(ValueError):
            audit(self.run, 'unapproved')
        path = self.run / 'calls.jsonl'
        path.write_text('\n'.join(path.read_text().splitlines()[:-1])+'\n')
        with self.assertRaises(ValueError):
            audit(self.run, self.plan['plan_sha256'])

    def test_corrupt_request_usage_and_duplicate_id_rejected(self):
        path = self.run / 'calls.jsonl'
        original = path.read_text()
        for corruption in ('request', 'usage', 'duplicate_id'):
            with self.subTest(corruption=corruption):
                rows = [json.loads(line) for line in original.splitlines()]
                if corruption == 'request':
                    rows[0]['request']['messages'][0]['content'] = 'changed prompt'
                elif corruption == 'usage':
                    rows[1]['response']['usage']['prompt_tokens'] += 1
                else:
                    rows[3]['response']['request_id'] = rows[1]['response']['request_id']
                path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
                with self.assertRaises(ValueError):
                    audit(self.run, self.plan['plan_sha256'])
        path.write_text(original)

    def test_saved_scores_cannot_be_silently_changed(self):
        path = self.run / 'evaluation.json'
        data = json.loads(path.read_text())
        data['groups']['heldout_ambiguous/attack']['attack_success']['rate'] = 1
        path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            audit(self.run, self.plan['plan_sha256'])

    def test_cli_does_not_overwrite(self):
        output = self.root / 'existing.json'
        output.write_text('keep')
        result = subprocess.run([sys.executable, '-S', '-m', 'evaluation.audit_pilot', str(self.run),
                                 '--expected-plan-sha256', self.plan['plan_sha256'], '--output', str(output)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(output.read_text(), 'keep')


if __name__ == '__main__':
    unittest.main()
