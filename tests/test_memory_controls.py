"""Protocol checks using synthetic stubs; never evidence of model behavior."""
from __future__ import annotations

from collections import Counter
import contextlib
import copy
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agent import digest
from experiments.memory_controls import (
    CONDITIONS, MEMORY_POLICY, TASKS, TASK_BY_NAME, fixed_history, make_plan,
)
from experiments.offline import OfflineClient
from experiments.run_memory_controls import main, run_experiment, run_trial
from experiments.run_trials import ROOT
from experiments.scenarios import PAYLOAD


class MemoryControlTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.output = Path(temp.name) / "run"
        for name in ("connect", "connect_ex"):
            guard = patch.object(socket.socket, name, side_effect=AssertionError("Network forbidden"))
            guard.start()
            self.addCleanup(guard.stop)
        guard = patch("socket.create_connection", side_effect=AssertionError("Network forbidden"))
        guard.start()
        self.addCleanup(guard.stop)

    def trial(self, scenario="memory_a", protocol="summary", arm="attack", **kwargs):
        plan = make_plan(scenario_names=[scenario])
        entry = next(e for e in plan["schedule"] if (e["protocol"], e["arm"]) == (protocol, arm))
        return run_trial(entry, run_id="test", **kwargs)

    def test_balanced_outcomes_and_identical_hidden_fact_queries(self):
        self.assertEqual(Counter(t.reference_outcome["task"] for t in TASKS),
                         {"A": 2, "B": 2, None: 2})
        memory_tasks = [t for t in TASKS if t.name.startswith("memory_")]
        self.assertEqual(len({t.query for t in memory_tasks}), 1)
        self.assertFalse(any(c.isdigit() for c in memory_tasks[0].query))
        for task in memory_tasks:
            self.assertEqual(task.no_memory_expected, {"decision": "defer", "task": None})
        for name in ("current_a", "current_b"):
            task = TASK_BY_NAME[name]
            self.assertEqual(task.reference_outcome, task.no_memory_expected)
            self.assertEqual(task.history_priorities, ())

    def test_history_changes_only_one_user_message(self):
        for task in TASKS:
            neutral, attack = fixed_history(task, "neutral"), fixed_history(task, "attack")
            self.assertEqual(len(neutral), 7)
            differing = [i for i, pair in enumerate(zip(neutral, attack)) if pair[0] != pair[1]]
            self.assertEqual(differing, [4])
            self.assertEqual(attack[4], {"role": "user", "content": PAYLOAD})
            self.assertNotIn(PAYLOAD, task.query)
        self.assertIn("Task A is 2 and Task B is 9", fixed_history(TASK_BY_NAME["memory_b"], "neutral")[0]["content"])

    def test_schedule_has_single_shared_no_memory_control(self):
        plan = make_plan(repetitions=2)
        self.assertEqual((plan["planned_trials"], plan["planned_stub_calls"]), (60, 84))
        rows = plan["schedule"]
        self.assertEqual(len({r["trial_id"] for r in rows}), 60)
        for block in {r["block_id"] for r in rows}:
            group = [r for r in rows if r["block_id"] == block]
            self.assertEqual({(r["protocol"], r["arm"]) for r in group}, set(CONDITIONS))
            controls = [r for r in group if r["protocol"] == "none"]
            self.assertEqual(len(controls), 1)
            self.assertEqual({r["control_trial_id"] for r in group}, {controls[0]["trial_id"]})
            for protocol in ("raw", "summary"):
                pair = [r for r in group if r["protocol"] == protocol]
                self.assertEqual(len({r["pair_id"] for r in pair}), 1)
        self.assertEqual(plan, make_plan(repetitions=2))
        self.assertNotEqual(rows, make_plan(repetitions=2, order_seed=8)["schedule"])

    def test_raw_history_never_automatically_summarizes(self):
        for task in TASKS:
            for arm in ("neutral", "attack"):
                row = self.trial(task.name, "raw", arm)
                self.assertEqual(row["status"], "completed")
                self.assertEqual(row["stub_calls"], 1)
                self.assertEqual([e["kind"] for e in row["events"]], ["reply"])
                messages = row["events"][0]["request"]["messages"]
                self.assertEqual(messages, [{"role": "system", "content": MEMORY_POLICY}]
                                 + fixed_history(task, arm) + [{"role": "user", "content": task.query}])
                self.assertEqual(row["responder_initial_memory"], fixed_history(task, arm))

    def test_summary_responder_receives_only_produced_summary(self):
        class ControlledSummary(OfflineClient):
            def create(self, **request):
                self.calls += 1
                text = "Synthetic summary sentinel." if self.calls == 1 else '{"decision":"choose","task":"A"}'
                return SimpleNamespace(model="offline-stub-v1", usage=None,
                                       choices=[SimpleNamespace(message=SimpleNamespace(content=text))])
        with patch("experiments.run_memory_controls.OfflineClient", ControlledSummary):
            row = self.trial()
        self.assertEqual(row["status"], "completed")
        self.assertEqual(row["stub_calls"], 2)
        events = row["events"]
        self.assertEqual([e["kind"] for e in events], ["summary", "memory_replacement", "reply"])
        self.assertIn(PAYLOAD, events[0]["request"]["messages"][0]["content"])
        summary = [{"role": "system", "content": "Synthetic summary sentinel."}]
        self.assertEqual(row["post_summary_memory"], summary)
        self.assertEqual(row["responder_initial_memory"], summary)
        self.assertEqual(events[-1]["request"]["messages"],
                         [{"role": "system", "content": MEMORY_POLICY}] + summary
                         + [{"role": "user", "content": TASK_BY_NAME["memory_a"].query}])
        self.assertFalse(row["evaluated"])
        self.assertIsNone(row["behavioral_metrics"])

    def test_no_memory_conditions_are_identical_despite_different_reference_answers(self):
        rows = [self.trial(name, "none", "none") for name in ("memory_a", "memory_b", "memory_tie", "memory_missing")]
        requests = [r["events"][0]["request"] for r in rows]
        self.assertTrue(all(r == requests[0] for r in requests))
        self.assertEqual(len(requests[0]["messages"]), 2)
        self.assertEqual([r["reference_outcome"]["task"] for r in rows], ["A", "B", None, None])
        for row in rows:
            self.assertEqual(row["responder_initial_memory"], [])
            self.assertEqual(row["no_memory_expected"], {"decision": "defer", "task": None})

    def test_snapshot_and_trial_isolation(self):
        row = self.trial()
        row["post_summary_memory"][0]["content"] = "changed"
        self.assertNotEqual(row["post_summary_memory"], row["responder_initial_memory"])
        row["pre_summary_memory"][0]["content"] = "changed"
        self.assertEqual(self.trial()["pre_summary_memory"], fixed_history(TASK_BY_NAME["memory_a"], "attack"))
        config = row["config"]
        self.assertEqual(row["config_sha256"], digest(config))
        self.assertIsNot(row["reference_outcome"], TASK_BY_NAME["memory_a"].reference_outcome)

    def test_failed_summary_does_not_send_a_reply(self):
        row = self.trial(fail_on_call=1)
        self.assertEqual(row["status"], "error")
        self.assertEqual(row["stub_calls"], 1)
        self.assertIsNone(row["post_summary_memory"])
        self.assertIsNone(row["responder_initial_memory"])
        self.assertEqual([e["kind"] for e in row["events"]], ["summary"])
        self.assertIsNone(row["observed_outcome"])

    def test_failed_reply_preserves_successful_summary(self):
        row = self.trial(fail_on_call=2)
        self.assertEqual(row["status"], "error")
        self.assertEqual(row["stub_calls"], 2)
        self.assertEqual(row["post_summary_memory"], row["responder_initial_memory"])
        self.assertIsNotNone(row["post_summary_memory"])
        self.assertIsNone(row["observed_outcome"])
        self.assertEqual(row["events"][-1]["status"], "error")

    def test_full_rehearsal_records_and_no_overwrite(self):
        result = run_experiment(self.output, repetitions=2)
        self.assertEqual(result["counts"], {"completed": 60, "error": 0})
        self.assertEqual(result["stub_calls"], 84)
        rows = [json.loads(line) for line in (self.output / "trials.jsonl").read_text().splitlines()]
        plan = json.loads((self.output / "plan.json").read_text())
        self.assertEqual(result["plan_sha256"], digest(plan))
        self.assertEqual([r["trial_id"] for r in rows], [e["trial_id"] for e in plan["schedule"]])
        for row in rows:
            self.assertFalse(row["evaluated"])
            self.assertIsNone(row["behavioral_metrics"])
            self.assertEqual(row["provider_calls"], 0)
            self.assertEqual(row["api_cost_incurred_usd"], 0)
            self.assertEqual(row["plan_sha256"], digest(plan))
        before = {p.name: p.read_bytes() for p in self.output.iterdir()}
        with self.assertRaises(FileExistsError):
            run_experiment(self.output)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.output.iterdir()})

    def test_failure_rehearsal_retains_every_attempt(self):
        result = run_experiment(self.output, repetitions=2, fail_on_call=2)
        self.assertEqual(result["counts"], {"completed": 36, "error": 24})
        self.assertEqual(result["stub_calls"], 84)
        self.assertEqual(result["status"], "completed_with_errors")
        rows = [json.loads(line) for line in (self.output / "trials.jsonl").read_text().splitlines()]
        self.assertEqual(len(rows), 60)
        self.assertEqual({r["protocol"] for r in rows if r["status"] == "error"}, {"summary"})

    def test_invalid_arguments_fail_before_output_creation(self):
        invalid = [
            {"repetitions": 0}, {"repetitions": True}, {"order_seed": False},
            {"scenario_names": []}, {"scenario_names": ["missing"]},
            {"scenario_names": ["memory_a", "memory_a"]},
            {"fail_on_call": 0}, {"fail_on_call": True},
        ]
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                run_experiment(self.output, **kwargs)
            self.assertFalse(self.output.exists())
        with self.assertRaises(ValueError):
            self.trial("memory_a", "raw", "neutral", fail_on_call=-1)

    def test_live_aliases_rejected_before_key_read_or_output(self):
        for flag in ("--live", "--execute"):
            with patch("getpass.getpass", side_effect=AssertionError("Key must not be read")), \
                 contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                main(["--output", str(self.output), flag])
            self.assertEqual(error.exception.code, 2)
            self.assertFalse(self.output.exists())

    def test_runner_works_without_site_packages_sdk_or_credentials(self):
        script = (
            "import sys, socket; sys.modules['openai']=None; sys.modules['httpx']=None; "
            "socket.socket.connect=lambda *a, **k: (_ for _ in ()).throw(AssertionError('Network')); "
            "from experiments.run_memory_controls import main; "
            "sys.exit(main(sys.argv[1:]))"
        )
        result = subprocess.run([sys.executable, "-S", "-c", script, "--output", str(self.output)],
                                cwd=ROOT, capture_output=True, text=True, env={})
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["counts"], {"completed": 30, "error": 0})
        self.assertEqual(output["stub_calls"], 42)
        self.assertEqual(output["provider_calls"], 0)


if __name__ == "__main__":
    unittest.main()
