"""Rehearse the fixed pilot offline; live execution requires explicit approval flags."""
from __future__ import annotations

import argparse
import copy
from datetime import date
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
import platform
import random
import sys
import uuid

from agent import SimpleAgent, CompletionFailed, digest
from evaluation.score import analyze
from experiments.offline import OfflineClient
from experiments.pilot_transport import GuardedClient, PilotStopped, append_record, build_sdk_client, now
from experiments.plan_pilot import pilot_plan


def validate_approval(plan, approved_hash, ceiling, *, today=None):
    """Bind a live invocation to reviewed source, prompts, settings and maximum cost."""
    unsigned = {k: v for k, v in plan.items() if k != "plan_sha256"}
    if approved_hash != plan.get("plan_sha256") or digest(unsigned) != approved_hash:
        raise ValueError("Approved plan hash does not match the supplied plan")
    if plan != pilot_plan():
        raise ValueError("Source/configuration changed; generate and review a fresh plan")
    today = today or date.today()
    age = (today - date.fromisoformat(plan["price_verified_on"])).days
    if not 0 <= age <= plan["approval_max_age_days"] or today >= date(2027, 1, 14):
        raise ValueError("Model/pricing verification expired; recheck before approval")
    amount = Decimal(str(ceiling))
    bounds = plan["budget"]
    if (not amount.is_finite()
            or not Decimal(bounds["conservative_run_reserve_usd"]) <= amount
            <= Decimal(bounds["proposed_spending_ceiling_usd"])):
        raise ValueError("Approved budget must cover the frozen run and not exceed $2.00")


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def make_schedule(plan, run_id):
    by_name = {}
    for condition in plan["matrix"]:
        by_name.setdefault(condition["scenario"], {})[condition["arm"]] = condition
    pairs = [(name, repetition) for name, arms in by_name.items()
             for repetition in range(1, arms["attack"]["repetitions"] + 1)]
    rng = random.Random(plan["order_seed"])
    rng.shuffle(pairs)
    schedule = []
    for name, repetition in pairs:
        arms = ["neutral", "attack"]
        rng.shuffle(arms)
        pair_id = f"{run_id}:{name}:{repetition}"
        for arm in arms:
            schedule.append({"pair_id": pair_id, "trial_id": f"{pair_id}:{arm}",
                             "repetition": repetition, "condition": copy.deepcopy(by_name[name][arm])})
    return schedule


def empty_record(item, plan, mode, run_id):
    c = item["condition"]
    config = {"mode": mode, "requested_model": plan["model"], "model_settings": plan["settings"],
              "scenario": c["scenario"], "arm": c["arm"], "repetition": item["repetition"],
              "protocol": "summary_only", "system_prompt": c["system_prompt"],
              "heldout_query": c["query"], "summary_strategy": "legacy_instruction_preserving",
              "summary_role": "system", "mitigation": "none", "synthetic_data_only": True,
              "model_seed": None, "max_memory_messages": 6, "plan_sha256": plan["plan_sha256"]}
    return {"schema_version": 2, "mode": mode, "run_id": run_id,
            "trial_id": item["trial_id"], "pair_id": item["pair_id"],
            "created_at": now(), "config": config, "config_sha256": digest(config),
            "provenance": plan["source_provenance"], "expected_outcome": c["expected"],
            "status": "unattempted", "error_type": None, "observed_outcome": None,
            "pre_summary_memory": None, "post_summary_memory": None, "events": [],
            "evaluated": False, "attack_success": None, "instruction_persistence": None,
            "legitimate_task_success": None}


def run_one(record, condition, plan, client):
    before_calls = client.dispatched
    client.trial_id = record["trial_id"]
    agents = []
    record["status"] = "running"
    try:
        summarizer = SimpleAgent(client=client, model=plan["model"],
                                 generation_settings=plan["settings"])
        agents.append(("summarizer", summarizer))
        summarizer.memory = copy.deepcopy(condition["history"])
        record["pre_summary_memory"] = copy.deepcopy(summarizer.memory)
        summarizer.summarize_memory()
        record["post_summary_memory"] = copy.deepcopy(summarizer.memory)
        first = summarizer.events[0]
        if client.mode == "live" and (first["finish_reason"] != "stop" or first["refusal"]):
            record["status"] = "invalid"
            return
        responder = SimpleAgent(client=client, model=plan["model"],
                                system_prompt=condition["system_prompt"],
                                generation_settings=plan["settings"])
        agents.append(("responder", responder))
        responder.memory = copy.deepcopy(summarizer.memory)
        record["observed_outcome"] = responder.chat(condition["query"])
        record["status"] = "completed"
    except (KeyboardInterrupt, SystemExit):
        record.update(status="error", error_type="Interrupted")
        client.halted = True
    except Exception as error:
        # Empty/refused text after a valid provider response is a model-invalid
        # attempt, whereas transport/usage/schema failures stop the entire run.
        if not (isinstance(error, CompletionFailed) and not client.halted):
            client.halted = True
        record["status"] = "error" if client.halted else "invalid"
        record["error_type"] = type(error).__name__
    finally:
        record["events"] = [{"phase": phase, **e} for phase, a in agents for e in a.events]
        calls = client.dispatched - before_calls
        record["provider_calls"] = calls if client.mode == "live" else 0
        record["stub_calls"] = calls if client.mode == "offline" else 0


def run_pilot(output, *, mode="offline", plan=None, approved_hash=None, ceiling="2.00", provider=None, prompt_key=False):
    plan = copy.deepcopy(plan or pilot_plan())
    if mode not in ("offline", "live"):
        raise ValueError("Unknown mode")
    if mode == "live":
        validate_approval(plan, approved_hash, ceiling)
    output = Path(output)
    # Validate/create the unique destination before SDK construction or key lookup.
    output.mkdir(parents=True, exist_ok=False)
    run_id = uuid.uuid4().hex
    schedule = make_schedule(plan, run_id)
    records = [empty_record(item, plan, mode, run_id) for item in schedule]
    manifest = {"mode": mode, "run_id": run_id, "created_at": now(), "status": "running",
                "python_version": platform.python_version(), "platform": platform.platform(),
                "plan_sha256": plan["plan_sha256"], "planned_trials": len(schedule),
                "approved_budget_usd": str(ceiling) if mode == "live" else None,
                "approved_plan_sha256": approved_hash if mode == "live" else None,
                "authorization_note": "CLI acknowledgement does not replace the owner's permission."}
    write_json(output / "plan.json", plan)
    write_json(output / "schedule.json", schedule)
    write_json(output / "manifest.json", manifest)
    client = None
    owned_provider = provider is None
    try:
        provider = provider if provider is not None else (build_sdk_client(plan, prompt_key=prompt_key) if mode == "live" else OfflineClient())
        with (output / "calls.jsonl").open("x", encoding="utf-8") as ledger, (output / "trials.jsonl").open("x", encoding="utf-8") as trials:
            client = GuardedClient(provider, plan, mode=mode, ceiling=ceiling, ledger=ledger)
            for item, record in zip(schedule, records):
                if not client.halted:
                    run_one(record, item["condition"], plan, client)
                append_record(trials, record)
        manifest["status"] = "aborted" if client.halted else "completed"
    except BaseException as error:
        manifest["status"] = "aborted"
        manifest["error_type"] = type(error).__name__
        manifest["setup_or_journal_error"] = str(error) if isinstance(error, PilotStopped) else None
        # An interrupted or disk-failed run is never resumed automatically. The
        # durable pre-call journal is authoritative if a trial write was lost.
        if not (output / "trials.jsonl").exists():
            with (output / "trials.jsonl").open("x", encoding="utf-8") as handle:
                for record in records:
                    append_record(handle, record)
    finally:
        if owned_provider and provider is not None and hasattr(provider, "close"):
            provider.close()
    counts = {status: sum(r["status"] == status for r in records)
              for status in ("completed", "invalid", "error", "unattempted")}
    summary = {"mode": mode, "run_id": run_id, "status": manifest["status"], "counts": counts,
               "attempted": len(records) - counts["unattempted"], "planned": len(records),
               "accounting": client.accounting() if client else None,
               "behavioral_metrics": None,
               "note": "Pipeline counts only; evaluate trials separately. Offline data is never model evidence."}
    # On a write failure these calls may also fail, leaving status running on
    # disk and the pre-call journal intact rather than declaring a clean finish.
    write_json(output / "summary.json", summary)
    write_json(output / "manifest.json", manifest)
    if "error_type" not in manifest:
        write_json(output / "evaluation.json", analyze(records))
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--approved-plan-sha256")
    parser.add_argument("--approved-budget-usd")
    parser.add_argument("--prompt-key", action="store_true", help="Hidden key entry in an interactive local terminal; never saved.")
    args = parser.parse_args(argv)
    approval_args = (args.plan, args.approved_plan_sha256, args.approved_budget_usd)
    if args.execute and not all(approval_args):
        parser.error("Live mode needs --plan, --approved-plan-sha256 and --approved-budget-usd after owner approval")
    if not args.execute and (any(approval_args) or args.prompt_key):
        parser.error("Approval flags apply only to explicit --execute mode")
    try:
        plan = json.loads(args.plan.read_text()) if args.plan else None
        result = run_pilot(args.output, mode="live" if args.execute else "offline", plan=plan,
                           approved_hash=args.approved_plan_sha256,
                           ceiling=args.approved_budget_usd or "2.00", prompt_key=args.prompt_key)
    except (ValueError, KeyError, OSError, InvalidOperation):
        parser.error("Invalid/stale approval, unavailable output path or malformed plan; no additional call authorized")
    print(json.dumps(result, indent=2))
    return 1 if result["status"] == "aborted" else 0


if __name__ == "__main__":
    sys.exit(main())
