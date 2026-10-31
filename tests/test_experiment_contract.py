"""Meaningful software checks; none assert live-model attack success."""
from __future__ import annotations

import ast
import contextlib
import copy
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch

from agent import SimpleAgent, CompletionFailed, BASE_SYSTEM_PROMPT, SUMMARY_PROMPT
from experiments.offline import OfflineClient
from experiments.run_trials import BASE_COMMIT, ROOT, main, run_experiment, run_trial
from experiments.scenarios import (
    SCENARIO_BY_NAME, ORIGINAL_INPUTS, PAYLOAD, conversation_inputs, fixed_history,
)


class RecordingClient(OfflineClient):
    def __init__(self):
        super().__init__()
        self.requests = []

    def create(self, **request):
        self.requests.append(copy.deepcopy(request))
        return super().create(**request)


class ExperimentContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "run"
        for name in ("connect", "connect_ex"):
            guard = patch.object(socket.socket, name, side_effect=AssertionError("Network forbidden"))
            guard.start()
            self.addCleanup(guard.stop)
        guard = patch("socket.create_connection", side_effect=AssertionError("Network forbidden"))
        guard.start()
        self.addCleanup(guard.stop)

    def trial(self, name="heldout_ambiguous", arm="attack", **kwargs):
        return run_trial(
            SCENARIO_BY_NAME[name], arm, run_id="test", pair_id="test-pair",
            repetition=1, provenance={"test": True}, **kwargs
        )

    def test_imports_without_openai_or_site_packages(self):
        script = (
            "import sys; sys.modules['openai']=None; "
            "import agent, attack_demo, experiments.run_trials, evaluation.score, experiments.plan_pilot; "
            "assert agent.SimpleAgent().memory == []"
        )
        result = subprocess.run([sys.executable, "-S", "-c", script], cwd=ROOT,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_missing_client_refuses_calls(self):
        agent = SimpleAgent()
        with self.assertRaises(CompletionFailed):
            agent.chat("Hello")
        self.assertEqual(agent.events[-1]["error_type"], "LiveCallsDisabled")

    def test_original_strings_are_unchanged(self):
        original = subprocess.check_output(
            ["git", "show", f"{BASE_COMMIT}:attack_demo.py"], cwd=ROOT, text=True
        )
        original_inputs = next(
            ast.literal_eval(n.value) for n in ast.parse(original).body
            if isinstance(n, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "inputs" for t in n.targets
            )
        )
        import attack_demo
        self.assertEqual(attack_demo.inputs, original_inputs)
        self.assertEqual(list(ORIGINAL_INPUTS), original_inputs)

    def test_requests_match_original_code_under_same_stub(self):
        original = subprocess.check_output(
            ["git", "show", f"{BASE_COMMIT}:agent.py"], cwd=ROOT, text=True
        )
        old_client = RecordingClient()
        fake_sdk = ModuleType("openai")
        fake_sdk.OpenAI = lambda: old_client
        scope = {}
        with patch.dict(sys.modules, {"openai": fake_sdk}):
            exec(compile(original, "original_agent.py", "exec"), scope)
        old_agent = scope["SimpleAgent"]()
        new_client = RecordingClient()
        new_agent = SimpleAgent(client=new_client)
        with contextlib.redirect_stdout(io.StringIO()):
            for message in ORIGINAL_INPUTS:
                self.assertEqual(old_agent.chat(message), new_agent.chat(message))
        self.assertEqual(old_client.requests, new_client.requests)
        self.assertEqual(old_agent.memory, new_agent.memory)
        self.assertEqual(new_agent.system_prompt, BASE_SYSTEM_PROMPT)

    def test_legacy_summary_timing_and_authority(self):
        agent = SimpleAgent(client=OfflineClient())
        for message in ORIGINAL_INPUTS:
            agent.chat(message)
        summaries = [e for e in agent.events if e["kind"] == "summary"]
        self.assertEqual([e["turn"] for e in summaries], [4, 7])
        self.assertIn(PAYLOAD, summaries[1]["request"]["messages"][0]["content"])
        replies = [e for e in agent.events if e["kind"] == "reply"]
        self.assertEqual([m["role"] for m in replies[6]["request"]["messages"]],
                         ["system", "system"])
        self.assertEqual(replies[-1]["request"]["messages"][-1]["content"], ORIGINAL_INPUTS[-1])
        self.assertTrue(summaries[0]["request"]["messages"][0]["content"].startswith(SUMMARY_PROMPT))

    def test_controls_differ_only_at_treatment(self):
        for builder, index in ((conversation_inputs, 5), (fixed_history, 4)):
            attack, neutral = builder("attack"), builder("neutral")
            self.assertEqual(len(attack), len(neutral))
            self.assertEqual([i for i, pair in enumerate(zip(attack, neutral))
                              if pair[0] != pair[1]], [index])
        self.assertEqual(conversation_inputs("attack")[-1], conversation_inputs("neutral")[-1])

    def test_heldout_queries_match_and_raw_history_is_absent(self):
        for name in ("heldout_ambiguous", "heldout_legitimate"):
            records = [self.trial(name, arm) for arm in ("attack", "neutral")]
            messages = []
            for record in records:
                reply = next(e for e in record["events"] if e["phase"] == "responder")
                assembled = reply["request"]["messages"]
                self.assertEqual([m["role"] for m in assembled], ["system", "system", "user"])
                self.assertEqual(assembled[1], record["post_summary_memory"][0])
                self.assertNotIn(PAYLOAD, assembled[-1]["content"])
                self.assertNotIn(ORIGINAL_INPUTS[-1], assembled[-1]["content"])
                messages.append(assembled)
            self.assertEqual(messages[0][-1], messages[1][-1])
            self.assertEqual(messages[0][0], messages[1][0])

    def test_agent_and_history_state_isolation(self):
        a = SimpleAgent(client=OfflineClient())
        a.chat("private-to-this-test")
        b = SimpleAgent(client=OfflineClient())
        self.assertEqual(b.memory, [])
        first = fixed_history("attack")
        first[0]["content"] = "mutated"
        self.assertNotEqual(first, fixed_history("attack"))

    def test_record_snapshots_are_detached(self):
        agent = SimpleAgent(client=OfflineClient())
        agent.chat("Original")
        observations = agent.events
        agent.memory[0]["content"] = "Changed"
        self.assertEqual(observations[0]["request"]["messages"][-1]["content"], "Original")
        observations[0]["request"]["messages"][-1]["content"] = "Tampered"
        self.assertEqual(agent.events[0]["request"]["messages"][-1]["content"], "Original")

    def test_failed_summary_does_not_replace_memory(self):
        agent = SimpleAgent(client=OfflineClient(fail_on_call=1))
        agent.memory = fixed_history("attack")
        before = copy.deepcopy(agent.memory)
        with self.assertRaises(CompletionFailed):
            agent.summarize_memory()
        self.assertEqual(agent.memory, before)
        self.assertEqual(agent.events[-1]["status"], "error")

    def test_invalid_provider_response_is_recorded(self):
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
            create=lambda **kw: SimpleNamespace(choices=[SimpleNamespace(
                message=SimpleNamespace(content=None))])
        )))
        agent = SimpleAgent(client=client)
        with self.assertRaises(CompletionFailed):
            agent.chat("test")
        self.assertEqual(agent.events[-1]["error_type"], "ValueError")

    def test_raw_provider_error_text_is_not_logged(self):
        def fail(**kwargs):
            raise RuntimeError("PRIVATE_ERROR_SENTINEL")
        client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=fail)))
        agent = SimpleAgent(client=client)
        with self.assertRaises(CompletionFailed) as error:
            agent.chat("synthetic")
        self.assertNotIn("PRIVATE_ERROR_SENTINEL", str(error.exception))
        self.assertNotIn("PRIVATE_ERROR_SENTINEL", json.dumps(agent.events))

    def test_offline_metrics_are_null_and_usage_unknown(self):
        record = self.trial()
        self.assertFalse(record["evaluated"])
        for name in ("attack_success", "instruction_persistence", "legitimate_task_success",
                     "token_usage"):
            self.assertIsNone(record[name])
        self.assertEqual(record["provider_calls"], 0)
        self.assertEqual(record["stub_calls"], 2)
        self.assertEqual(record["events"][0]["returned_model"], "offline-stub-v1")

    def test_end_to_end_pairs_and_files(self):
        summary = run_experiment(self.path, repetitions=2, order_seed=7)
        records = [json.loads(line) for line in (self.path / "trials.jsonl").read_text().splitlines()]
        self.assertEqual(len(records), 12)
        self.assertEqual(summary["completed"], 12)
        self.assertEqual(len({r["trial_id"] for r in records}), 12)
        pairs = {}
        for record in records:
            pairs.setdefault(record["pair_id"], set()).add(record["config"]["arm"])
            self.assertTrue(record["provenance"]["source_sha256"])
        self.assertEqual(len(pairs), 6)
        self.assertTrue(all(arms == {"attack", "neutral"} for arms in pairs.values()))
        self.assertIsNone(summary["attack_success_rate"])
        self.assertEqual(json.loads((self.path / "manifest.json").read_text())["status"], "completed")

    def test_all_attempts_retained_after_stub_failures(self):
        summary = run_experiment(self.path, fail_on_call=1)
        records = [json.loads(line) for line in (self.path / "trials.jsonl").read_text().splitlines()]
        self.assertEqual(summary["attempted"], 6)
        self.assertEqual(summary["errors"], 6)
        self.assertEqual(len(records), 6)
        self.assertTrue(all(r["status"] == "error" for r in records))
        self.assertTrue(all(any(e["status"] == "error" for e in r["events"]) for r in records))
        self.assertEqual(json.loads((self.path / "manifest.json").read_text())["status"],
                         "completed_with_errors")

    def test_existing_results_are_never_overwritten(self):
        run_experiment(self.path)
        before = (self.path / "trials.jsonl").read_bytes()
        with self.assertRaises(FileExistsError):
            run_experiment(self.path)
        self.assertEqual((self.path / "trials.jsonl").read_bytes(), before)

    def test_live_cli_fails_before_creating_output(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                main(["--live", "--output", str(self.path)])
        self.assertEqual(error.exception.code, 2)
        self.assertFalse(self.path.exists())

    def test_failure_cli_reports_nonzero_status(self):
        with contextlib.redirect_stdout(io.StringIO()):
            status = main(["--output", str(self.path), "--fail-on-call", "2"])
        self.assertEqual(status, 1)
        self.assertEqual(json.loads((self.path / "summary.json").read_text())["errors"], 6)

    def test_invalid_configuration_does_not_create_artifacts(self):
        with self.assertRaises(ValueError):
            run_experiment(self.path, repetitions=0)
        self.assertFalse(self.path.exists())
        with self.assertRaises(ValueError):
            run_experiment(self.path, scenario_names=["original_direct", "original_direct"])
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()
