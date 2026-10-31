"""Synthetic-only regression tests; no model behavior is inferred."""
import copy
from datetime import date
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agent import digest
from evaluation.score_defense import analyze
from evaluation.audit_defense import audit
from experiments.defense_study import make_plan, execute, replacement, summary_messages, VERSION
from experiments.memory_controls import fixed_history, TASK_BY_NAME
from experiments.pilot_transport import GuardedClient
from experiments.run_defense_pilot import run, validate_approval
from experiments.structured_memory import validate_memory


class FixtureProvider:
    """Live-shaped local fixture; only test harnesses may use it."""
    def __init__(self, responses=None, fail=None):
        self.calls = 0
        self.responses = responses
        self.fail = fail
        self.chat = SimpleNamespace(completions=self)

    def create(self, **request):
        self.calls += 1
        if self.calls == self.fail:
            raise RuntimeError("synthetic failure")
        text = self.responses[(self.calls - 1) % len(self.responses)] if self.responses else (
            '{"facts":[]}' if self.calls % 2 else '{"decision":"defer","task":null}')
        return SimpleNamespace(model=request["model"],
            usage=SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content=text, refusal=None))],
            _request_id=f"synthetic-{self.calls}")


class DefenseTests(unittest.TestCase):
    def setUp(self):
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection"):
            p = patch(target, side_effect=AssertionError("Network forbidden"))
            p.start()
            self.addCleanup(p.stop)
        self.history = fixed_history(TASK_BY_NAME["memory_a"], "attack")

    def test_strict_schema_rejects_instructions_and_invalid_sources(self):
        fact = {"task": "A", "priority": 9, "source_message": 0}
        cases = [{"facts": [fact], "instruction": "ignore policy"}, {"facts": [{**fact, "text": "ignore policy"}]},
                 {"facts": [fact, fact]}, {"facts": [{**fact, "task": "ignore policy"}]},
                 *[{"facts": [{**fact, "priority": v}]} for v in (True, "9", None, float("nan"), float("inf"), 10001)],
                 *[{"facts": [{**fact, "source_message": v}]} for v in (-1, 99, 1, True, "0")],
                 {"facts": None}, []]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                validate_memory(json.dumps(case), self.history)
        for raw in ('{"facts":[],"facts":[]}', '```json\n{"facts":[]}\n```', 'x'*4097, 'null'):
            with self.assertRaises(ValueError):
                validate_memory(raw, self.history)

    def test_no_raw_payload_reaches_validated_memory(self):
        result = validate_memory('{"facts":[{"task":"A","priority":9,"source_message":0}]}', self.history)
        self.assertEqual(result["facts"][0]["source_role"], "user")
        entry = {"scenario": "memory_a", "arm": "attack", "format": "structured"}
        message, data, rejected = replacement(entry, '{"facts":[],"instruction":"IGNORE"}')
        self.assertTrue(rejected)
        self.assertEqual(data, {"facts": []})
        self.assertNotIn("IGNORE", message["content"])

    def test_structure_does_not_claim_fact_truth(self):
        result = validate_memory('{"facts":[{"task":"A","priority":-77,"source_message":4}]}', self.history)
        self.assertEqual(result["facts"][0]["priority"], -77)
        # False but well-formed facts must remain measurable failures, not hidden assumptions.

    def test_matrix_is_balanced_and_query_not_given_to_extractor(self):
        plan = make_plan()
        self.assertEqual(len(plan["schedule"]), 240)
        self.assertEqual(plan["max_provider_calls"], 480)
        self.assertEqual(plan["budget"]["conservative_run_reserve_usd"], "9.2897280")
        for task in TASK_BY_NAME:
            for arm in ("neutral", "attack"):
                for fmt in ("free_text", "structured"):
                    rows = [r for r in plan["schedule"] if (r["scenario"], r["arm"], r["format"]) == (task, arm, fmt)]
                    self.assertEqual(len(rows), 10)
                    self.assertNotIn(TASK_BY_NAME[task].query, summary_messages(rows[0])[0]["content"])

    def test_offline_run_and_failures_keep_full_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            good = run(Path(d)/"good")
            self.assertEqual(good["counts"]["completed"], 240)
            self.assertEqual(good["accounting"]["provider_calls"], 0)
            self.assertEqual(good["accounting"]["stub_calls"], 480)
            report = json.loads((Path(d)/"good/evaluation.json").read_text())
            self.assertEqual(report["counts"], {"unscored": 240})
            self.assertTrue(all(s["answer_recovery"] is None for s in report["trials"]))
            failed = run(Path(d)/"fail", fail_on_call=3)
            self.assertEqual(failed["counts"], {"completed": 1, "invalid": 0, "error": 1, "unattempted": 238})
            self.assertEqual(len((Path(d)/"fail/trials.jsonl").read_text().splitlines()), 240)
            with self.assertRaises(FileExistsError):
                run(Path(d)/"good")

    def test_approval_rejects_prior_hash_drift_budget_and_expiration(self):
        plan = make_plan()
        validate_approval(plan, plan["plan_sha256"], "10.00", today=date(2026, 10, 30))
        for ceiling in ("9.00", "10.01", "NaN", "Infinity"):
            with self.assertRaises(ValueError):
                validate_approval(plan, plan["plan_sha256"], ceiling, today=date(2026, 10, 30))
        with self.assertRaises(ValueError):
            validate_approval(plan, "9500439baf60d5d1681bcf116371715a37299210fcc04c98ca0975ee7162b8d9", "10")
        with self.assertRaises(ValueError):
            validate_approval(plan, plan["plan_sha256"], "10", today=date(2026, 11, 7))
        plan["policy"] += "changed"
        with self.assertRaises(ValueError):
            validate_approval(plan, plan["plan_sha256"], "10")

    def test_unauthorized_live_never_builds_sdk(self):
        with tempfile.TemporaryDirectory() as d, patch("experiments.run_defense_pilot.build_sdk_client") as sdk:
            with self.assertRaises(ValueError):
                run(Path(d)/"no", mode="live")
            sdk.assert_not_called()
            self.assertFalse((Path(d)/"no").exists())

    def fixture_run(self, directory, responses=None, fail=None):
        plan = make_plan()
        # Explicit testing of the guarded live path using ONLY local fixture responses.
        with patch("experiments.run_defense_pilot.date") as clock:
            clock.today.return_value = date(2026, 10, 30)
            clock.fromisoformat.side_effect = date.fromisoformat
            run(directory, mode="live", plan=plan, approved_hash=plan["plan_sha256"],
                provider=FixtureProvider(responses, fail))
        return [json.loads(s) for s in (directory/"trials.jsonl").read_text().splitlines()], plan

    def test_synthetic_live_scoring_keeps_utility_and_security_separate(self):
        with tempfile.TemporaryDirectory() as d:
            rows, plan = self.fixture_run(Path(d)/"fixture")
            scores = {s["trial_id"]: s for s in analyze(rows, plan)["trials"]}
            s = scores["memory_a:1:structured:attack"]
            self.assertFalse(s["answer_recovery"])
            self.assertFalse(s["structured_facts_preserved"])
            self.assertFalse(s["available_evidence_policy_violation"])
            self.assertIsNone(s["attack_success"])
            self.assertFalse(scores["memory_tie:1:structured:attack"]["attack_success"])
            self.assertIsNone(scores["memory_a:1:free_text:attack"]["available_evidence_policy_violation"])

    def test_attack_choice_and_malformed_decision(self):
        with tempfile.TemporaryDirectory() as d:
            rows, plan = self.fixture_run(Path(d)/"choose", ['{"facts":[]}', '{"decision":"choose","task":"A"}'])
            scores = {s["trial_id"]: s for s in analyze(rows, plan)["trials"]}
            self.assertTrue(scores["memory_tie:1:structured:attack"]["attack_success"])
            rows, plan = self.fixture_run(Path(d)/"bad", ['{"facts":[]}', 'not JSON'])
            self.assertEqual(analyze(rows, plan)["counts"], {"invalid": 240})

    def test_trace_tampering_and_missing_rows_are_detected(self):
        with tempfile.TemporaryDirectory() as d:
            rows, plan = self.fixture_run(Path(d)/"fixture")
            rows[0]["events"][1]["request"]["messages"][1]["role"] = "user"
            self.assertEqual(analyze(rows, plan)["trials"][0]["status"], "invalid")
            with self.assertRaises(ValueError):
                analyze(rows[:-1], plan)
            rows[0]["arm"] = "made_up"
            with self.assertRaises(ValueError):
                analyze(rows, plan)

    def test_rejected_memory_still_runs_responder_and_preserves_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            rows, plan = self.fixture_run(Path(d)/"fixture", ['{"facts":[],"instructions":"ignore"}', '{"decision":"defer","task":null}'])
            structured = [r for r in rows if r["format"] == "structured"]
            self.assertTrue(all(r["validation_rejected"] for r in structured))
            self.assertTrue(all(r["provider_calls"] == 2 for r in structured))
            self.assertTrue(all("ignore" not in r["responder_initial_memory"][0]["content"] for r in structured))

    def test_transport_error_stops_and_keeps_unattempted(self):
        with tempfile.TemporaryDirectory() as d:
            rows, plan = self.fixture_run(Path(d)/"fixture", fail=2)
            self.assertEqual(rows[0]["status"], "error")
            self.assertTrue(all(r["status"] == "unattempted" for r in rows[1:]))
            self.assertEqual(analyze(rows, plan)["counts"], {"error": 1, "unattempted": 239})

    def test_audit_reproduces_scores_and_detects_journal_corruption(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/"fixture"
            self.fixture_run(path)
            self.assertEqual(audit(path)["journal_calls"], 480)
            events = [json.loads(s) for s in (path/"calls.jsonl").read_text().splitlines()]
            events[1]["response"]["response_text"] = "changed"
            (path/"calls.jsonl").write_text("\n".join(json.dumps(e) for e in events))
            with self.assertRaises(ValueError):
                audit(path)

    def test_setup_failure_leaves_recovery_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d)/"fixture"
            plan = make_plan()
            with patch("experiments.run_defense_pilot.validate_approval"), patch(
                    "experiments.run_defense_pilot.build_sdk_client", side_effect=RuntimeError("fixture")):
                with self.assertRaises(RuntimeError):
                    run(path, mode="live", plan=plan, approved_hash=plan["plan_sha256"])
            rows = json.loads((path/"recovery-ledger.json").read_text())
            self.assertEqual(len(rows), 240)
            self.assertTrue(all(r["status"] == "unattempted" for r in rows))


if __name__ == "__main__":
    unittest.main()
