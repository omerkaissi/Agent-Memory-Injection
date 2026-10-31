"""Offline-first matched trial runner. Live execution is deliberately disabled."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import subprocess
import sys
import uuid
from datetime import datetime, timezone

from agent import SimpleAgent, DEFAULT_MODEL, digest
from experiments.offline import OfflineClient
from experiments.scenarios import SCENARIOS, SCENARIO_BY_NAME, conversation_inputs, fixed_history

BASE_COMMIT = "fcdf5c74ed35d71e32113155f44302139cac2848"
ROOT = Path(__file__).resolve().parents[1]


def source_provenance():
    def git(*args):
        try:
            return subprocess.check_output(
                ["git", "-C", str(ROOT), *args], stderr=subprocess.DEVNULL, text=True
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            return None
    status = git("status", "--porcelain")
    sources = [ROOT / "agent.py", ROOT / "attack_demo.py",
               ROOT / "requirements.txt", *sorted((ROOT / "experiments").glob("*.py")),
               *sorted((ROOT / "evaluation").glob("*.py")),
               *sorted(ROOT.glob("requirements-lock.txt")),
               *sorted((ROOT / "docs").glob("*.md"))]
    return {
        "baseline_commit": BASE_COMMIT, "code_commit": git("rev-parse", "HEAD"),
        "working_tree_dirty": None if status is None else bool(status),
        "source_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sources
        },
    }


def run_trial(scenario, arm, *, run_id, pair_id, repetition, provenance,
              fail_on_call=None):
    client = OfflineClient(fail_on_call=fail_on_call)
    config = {
        "mode": "offline", "requested_model": DEFAULT_MODEL,
        "model_settings": {}, "model_settings_note": "No explicit generation parameters.",
        "scenario": scenario.name, "protocol": scenario.protocol,
        "arm": arm, "repetition": repetition, "max_memory_messages": 6,
        "summary_strategy": "legacy_instruction_preserving",
        "summary_role": "system", "system_prompt": scenario.system_prompt,
        "heldout_query": scenario.query, "mitigation": "none",
        "synthetic_data_only": True, "model_seed": None, "fail_on_call": fail_on_call,
    }
    record = {
        "schema_version": 1, "run_id": run_id, "pair_id": pair_id,
        "trial_id": f"{pair_id}:{arm}", "created_at": datetime.now(timezone.utc).isoformat(),
        "mode": "offline", "config": config, "config_sha256": digest(config),
        "provenance": provenance, "purpose": scenario.purpose,
        "expected_outcome": scenario.expected, "observed_outcome": None,
        "status": "pending", "error_type": None, "events": [],
        "pre_summary_memory": None, "post_summary_memory": None,
        "evaluated": False, "attack_success": None, "instruction_persistence": None,
        "legitimate_task_success": None,
        "evaluation_note": "Offline stubs verify plumbing only; model metrics are not computed.",
        "provider_calls": 0, "api_cost_incurred_usd": 0.0,
        "token_usage": None, "stub_calls": 0,
    }
    summarizer = None
    responder = None
    try:
        if scenario.protocol == "conversation":
            responder = SimpleAgent(client=client, system_prompt=scenario.system_prompt)
            for user_input in conversation_inputs(arm):
                record["observed_outcome"] = responder.chat(user_input)
        else:
            summarizer = SimpleAgent(client=client)
            summarizer.memory = fixed_history(arm)
            record["pre_summary_memory"] = copy.deepcopy(summarizer.memory)
            summarizer.summarize_memory()
            record["post_summary_memory"] = copy.deepcopy(summarizer.memory)
            # No raw conversation or earlier assistant replies reach the new object.
            responder = SimpleAgent(client=client, system_prompt=scenario.system_prompt)
            responder.memory = copy.deepcopy(summarizer.memory)
            record["observed_outcome"] = responder.chat(scenario.query)
        record["status"] = "completed"
    except Exception as error:
        record["status"] = "error"
        record["observed_outcome"] = None
        record["error_type"] = type(error).__name__
    finally:
        if scenario.protocol == "conversation":
            record["events"] = [
                {"phase": "conversation", **e} for e in (responder.events if responder else [])
            ]
            replacements = [e for e in record["events"] if e["kind"] == "memory_replacement"]
            if replacements:
                record["pre_summary_memory"] = replacements[-1]["before"]
                record["post_summary_memory"] = replacements[-1]["after"]
        else:
            record["events"] = [
                {"phase": "summarizer", **e} for e in (summarizer.events if summarizer else [])
            ] + [
                {"phase": "responder", **e} for e in (responder.events if responder else [])
            ]
        record["stub_calls"] = client.calls
    return record


def run_experiment(output, *, repetitions=1, order_seed=0,
                   scenario_names=None, fail_on_call=None):
    if repetitions < 1:
        raise ValueError("repetitions must be positive")
    if fail_on_call is not None and fail_on_call < 1:
        raise ValueError("fail_on_call must be positive")
    names = scenario_names or [s.name for s in SCENARIOS]
    if len(set(names)) != len(names):
        raise ValueError("Each scenario must be selected once")
    selected = [SCENARIO_BY_NAME[name] for name in names]
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    run_id = uuid.uuid4().hex
    provenance = source_provenance()
    rng = random.Random(order_seed)
    schedule = [(scenario, repetition) for scenario in selected
                for repetition in range(1, repetitions + 1)]
    rng.shuffle(schedule)
    counts = {}
    manifest = {
        "schema_version": 1, "run_id": run_id, "mode": "offline",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "order_seed": order_seed, "repetitions": repetitions,
        "scenario_names": names, "planned_trials": len(schedule) * 2,
        "provenance": provenance, "status": "running", "live_execution_enabled": False,
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    with (output / "trials.jsonl").open("x", encoding="utf-8") as handle:
        for scenario, repetition in schedule:
            pair_id = f"{run_id}:{scenario.name}:{repetition}"
            arms = ["neutral", "attack"]
            rng.shuffle(arms)
            for arm in arms:
                record = run_trial(
                    scenario, arm, run_id=run_id, pair_id=pair_id, repetition=repetition,
                    provenance=provenance, fail_on_call=fail_on_call,
                )
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                handle.flush()
                group = counts.setdefault(
                    f"{scenario.name}/{arm}", {"attempted": 0, "completed": 0, "errors": 0}
                )
                group["attempted"] += 1
                group["completed" if record["status"] == "completed" else "errors"] += 1
    summary = {
        "mode": "offline", "run_id": run_id, "groups": counts,
        "attempted": sum(g["attempted"] for g in counts.values()),
        "completed": sum(g["completed"] for g in counts.values()),
        "errors": sum(g["errors"] for g in counts.values()),
        "provider_calls": 0, "api_cost_incurred_usd": 0.0,
        "attack_success_rate": None, "instruction_persistence_rate": None,
        "legitimate_task_success_rate": None,
        "interpretation": "Software checks only. No inference about model behavior.",
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    manifest["status"] = "completed_with_errors" if summary["errors"] else "completed"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--order-seed", type=int, default=0,
                        help="Seed for trial order only, not a model seed.")
    parser.add_argument("--scenario", choices=list(SCENARIO_BY_NAME), action="append")
    parser.add_argument("--fail-on-call", type=int, help="Inject a stub failure within each trial.")
    parser.add_argument("--live", action="store_true", help="Reserved; currently refuses all live runs.")
    args = parser.parse_args(argv)
    if args.live:
        parser.error("Live calls are disabled pending a separately approved model and budget.")
    try:
        result = run_experiment(
            args.output, repetitions=args.repetitions, order_seed=args.order_seed,
            scenario_names=args.scenario, fail_on_call=args.fail_on_call,
        )
    except (ValueError, FileExistsError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
