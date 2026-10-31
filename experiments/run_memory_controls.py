"""Offline rehearsal of memory-dependent tasks with no/raw/summary memory controls."""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import uuid

from agent import CompletionFailed, SimpleAgent, digest
from experiments.memory_controls import (
    CONDITIONS, GENERATION_SETTINGS, MEMORY_POLICY, REQUESTED_MODEL, STUDY_VERSION,
    TASK_BY_NAME, fixed_history, make_plan,
)
from experiments.offline import OfflineClient
from experiments.run_trials import source_provenance


def validate_failure(fail_on_call):
    if fail_on_call is not None and (type(fail_on_call) is not int or fail_on_call < 1):
        raise ValueError("fail_on_call must be a positive integer")


def trial_config(entry, *, mode="offline", fail_on_call=None):
    if mode not in ("offline", "live"):
        raise ValueError("Unknown data mode")
    task = TASK_BY_NAME[entry["scenario"]]
    protocol, arm = entry["protocol"], entry["arm"]
    if (protocol, arm) not in CONDITIONS:
        raise ValueError("Unknown protocol/arm combination")
    # A seven-message raw history plus one query must not trigger automatic compression.
    responder_limit = 8 if protocol == "raw" else 6
    return {
        "study_version": STUDY_VERSION, "mode": mode, **copy.deepcopy(entry),
        "system_prompt": MEMORY_POLICY, "heldout_query": task.query,
        "requested_model": REQUESTED_MODEL, "generation_settings": dict(GENERATION_SETTINGS),
        "model_seed": None, "responder_max_memory_messages": responder_limit,
        "summary_strategy": "legacy_instruction_preserving" if protocol == "summary" else None,
        "summary_role": "system" if protocol == "summary" else None,
        "mitigation": "none", "synthetic_data_only": True, "fail_on_call": fail_on_call,
    }


def empty_record(entry, *, run_id, mode="offline", fail_on_call=None):
    config = trial_config(entry, mode=mode, fail_on_call=fail_on_call)
    task = TASK_BY_NAME[entry["scenario"]]
    record = {
        "schema_version": f"memory-controls-{mode}-1", "run_id": run_id,
        **copy.deepcopy(entry), "mode": mode, "config": config,
        "config_sha256": digest(config), "purpose": task.purpose,
        "reference_outcome": task.reference_outcome,
        "no_memory_expected": task.no_memory_expected,
        "status": "pending", "error_type": None, "observed_outcome": None,
        "pre_summary_memory": None, "post_summary_memory": None,
        "responder_initial_memory": None, "events": [], "stub_calls": 0,
        "provider_calls": 0, "api_cost_incurred_usd": 0.0,
        "evaluated": False, "behavioral_metrics": None,
        "evaluation_note": "Score separately. Offline text is never model evidence; reference outcomes describe input facts.",
    }
    return record


def execute_trial(record, client):
    """Shared protocol; transport/approval gates belong to the calling runner."""
    config = record["config"]
    task = TASK_BY_NAME[config["scenario"]]
    protocol, arm = config["protocol"], config["arm"]
    live = record["mode"] == "live"
    if live and getattr(client, "offline_only", False):
        raise ValueError("Offline client cannot produce live records")
    before_calls = getattr(client, "dispatched", getattr(client, "calls", 0))
    summarizer = responder = None
    try:
        memory = [] if protocol == "none" else fixed_history(task, arm)
        if protocol == "summary":
            summarizer = SimpleAgent(client=client, model=REQUESTED_MODEL,
                                     generation_settings=GENERATION_SETTINGS)
            summarizer.memory = copy.deepcopy(memory)
            record["pre_summary_memory"] = copy.deepcopy(memory)
            summarizer.summarize_memory()
            memory = copy.deepcopy(summarizer.memory)
            record["post_summary_memory"] = copy.deepcopy(memory)
            event = summarizer.events[0]
            if live and (event["finish_reason"] != "stop" or event["refusal"]):
                record["status"] = "invalid"
                return record
        responder = SimpleAgent(client=client, model=REQUESTED_MODEL,
                                system_prompt=MEMORY_POLICY, max_memory=config["responder_max_memory_messages"],
                                generation_settings=GENERATION_SETTINGS)
        responder.memory = copy.deepcopy(memory)
        record["responder_initial_memory"] = copy.deepcopy(memory)
        record["observed_outcome"] = responder.chat(task.query)
        event = responder.events[-1]
        record["status"] = ("invalid" if live and
                            (event["finish_reason"] != "stop" or event["refusal"]) else "completed")
    except (KeyboardInterrupt, SystemExit):
        if not live:
            raise
        record.update(status="error", error_type="Interrupted")
        client.halted = True
    except Exception as error:
        if live and not isinstance(error, CompletionFailed):
            client.halted = True
        record["status"] = "invalid" if live and not client.halted else "error"
        record["error_type"] = type(error).__name__
    finally:
        record["events"] = [
            {"phase": "summarizer", **event} for event in (summarizer.events if summarizer else [])
        ] + [
            {"phase": "responder", **event} for event in (responder.events if responder else [])
        ]
        calls = getattr(client, "dispatched", getattr(client, "calls", 0)) - before_calls
        record["provider_calls" if live else "stub_calls"] = calls
        record["api_cost_incurred_usd"] = None if live else 0.0
    return record


def run_trial(entry, *, run_id, fail_on_call=None):
    validate_failure(fail_on_call)
    record = empty_record(entry, run_id=run_id, fail_on_call=fail_on_call)
    return execute_trial(record, OfflineClient(fail_on_call=fail_on_call))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_experiment(output, *, repetitions=1, order_seed=7, scenario_names=None, fail_on_call=None):
    validate_failure(fail_on_call)
    plan = make_plan(repetitions=repetitions, order_seed=order_seed, scenario_names=scenario_names)
    plan["fail_on_call"] = fail_on_call
    plan["provenance"] = source_provenance()
    plan_hash = digest(plan)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    run_id = uuid.uuid4().hex
    manifest = {
        "schema_version": "memory-controls-offline-1", "run_id": run_id,
        "study_version": STUDY_VERSION, "mode": "offline", "status": "running",
        "created_at": datetime.now(timezone.utc).isoformat(), "plan_sha256": plan_hash,
        "live_execution_enabled": False, "provenance": plan["provenance"],
        "planned_trials": plan["planned_trials"], "planned_stub_calls": plan["planned_stub_calls"],
    }
    write_json(output / "plan.json", plan)
    write_json(output / "manifest.json", manifest)
    counts = {"completed": 0, "error": 0}
    stub_calls = 0
    with (output / "trials.jsonl").open("x", encoding="utf-8") as handle:
        for entry in plan["schedule"]:
            record = run_trial(entry, run_id=run_id, fail_on_call=fail_on_call)
            record["plan_sha256"] = plan_hash
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            counts[record["status"]] += 1
            stub_calls += record["stub_calls"]
    manifest["status"] = "completed_with_errors" if counts["error"] else "completed"
    summary = {
        "study_version": STUDY_VERSION, "mode": "offline", "run_id": run_id,
        "status": manifest["status"], "plan_sha256": plan_hash,
        "planned": plan["planned_trials"], "attempted": sum(counts.values()),
        "counts": counts, "stub_calls": stub_calls, "provider_calls": 0,
        "api_cost_incurred_usd": 0.0, "behavioral_metrics": None,
        "note": "Software rehearsal only; no model behavior or mitigation effectiveness measured.",
    }
    write_json(output / "summary.json", summary)
    write_json(output / "manifest.json", manifest)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--order-seed", type=int, default=7)
    parser.add_argument("--scenario", choices=list(TASK_BY_NAME), action="append")
    parser.add_argument("--fail-on-call", type=int, help="Inject a stub failure within each trial.")
    parser.add_argument("--live", "--execute", action="store_true", dest="live",
                        help="Reserved: this study has no live execution path.")
    args = parser.parse_args(argv)
    if args.live:
        parser.error("This study is offline-only. No live runner, scoring contract or paid approval exists.")
    try:
        summary = run_experiment(args.output, repetitions=args.repetitions, order_seed=args.order_seed,
                                 scenario_names=args.scenario, fail_on_call=args.fail_on_call)
    except (ValueError, FileExistsError) as error:
        parser.error(str(error))
    print(json.dumps(summary, indent=2))
    return 1 if summary["counts"]["error"] else 0


if __name__ == "__main__":
    sys.exit(main())
