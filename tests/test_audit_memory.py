"""Synthetic journal corruption checks; no provider requests."""
import contextlib
import io
import json
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import patch

from evaluation.audit_memory import audit, main
from experiments.plan_memory_pilot import memory_pilot_plan
from experiments.run_memory_pilot import run_pilot
from test_audit_pilot import FakeProvider


class MemoryAuditTests(unittest.TestCase):
    def setUp(self):
        for target in ('socket.socket.connect','socket.socket.connect_ex','socket.create_connection'):
            p=patch(target,side_effect=AssertionError('Network forbidden'));p.start();self.addCleanup(p.stop)
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.root=Path(temp.name);self.run=self.root/'synthetic';self.plan=memory_pilot_plan()
        run_pilot(self.run,mode='live',plan=self.plan,approved_hash=self.plan['plan_sha256'],provider=FakeProvider())

    def test_complete_mixed_protocol_run_preserves_raw(self):
        before={p.name:p.read_bytes() for p in self.run.iterdir()}
        result=audit(self.run,self.plan['plan_sha256'])
        self.assertEqual(result['trials'],300);self.assertEqual(result['provider_calls'],420)
        self.assertEqual(result['journal_entries'],840);self.assertEqual(result['unique_request_ids'],420)
        self.assertEqual(result['token_totals']['prompt_tokens'],42000)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.run.iterdir()})

    def test_corrupt_or_incomplete_journal_rejected(self):
        p=self.run/'calls.jsonl';original=p.read_text()
        for mode in ('missing','request','usage','request_id','reservation'):
            rows=[json.loads(s) for s in original.splitlines()]
            if mode=='missing':rows.pop()
            elif mode=='request':rows[0]['request']['messages'][0]['content']='changed'
            elif mode=='usage':rows[1]['response']['usage']['prompt_tokens']+=1
            elif mode=='request_id':rows[3]['response']['request_id']=rows[1]['response']['request_id']
            else:rows[0]['reserved_usd']='0'
            p.write_text(''.join(json.dumps(r)+'\n' for r in rows))
            with self.subTest(mode=mode),self.assertRaises(ValueError):audit(self.run,self.plan['plan_sha256'])
        p.write_text(original)

    def test_wrong_approval_changed_score_and_reordered_schedule_rejected(self):
        with self.assertRaises(ValueError):audit(self.run,'wrong-hash')
        p=self.run/'evaluation.json';original=p.read_text();data=json.loads(original);data['counts']['valid']=299
        p.write_text(json.dumps(data))
        with self.assertRaises(ValueError):audit(self.run,self.plan['plan_sha256'])
        p.write_text(original)
        p=self.run/'schedule.json';data=json.loads(p.read_text());data.reverse();p.write_text(json.dumps(data))
        with self.assertRaises(ValueError):audit(self.run,self.plan['plan_sha256'])

    def test_existing_output_is_never_replaced(self):
        out=self.root/'keep.json';out.write_text('keep')
        with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit):
            main([str(self.run),'--expected-plan-sha256',self.plan['plan_sha256'],'--output',str(out)])
        self.assertEqual(out.read_text(),'keep')


if __name__=='__main__':unittest.main()
