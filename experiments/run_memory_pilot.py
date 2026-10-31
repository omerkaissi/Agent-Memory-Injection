"""Bounded memory-control pilot: offline by default; live requires exact approval."""
from __future__ import annotations

import argparse
import copy
from datetime import date
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import sys
import uuid

from agent import digest
from evaluation.score_memory import analyze
from experiments.offline import OfflineClient
from experiments.pilot_transport import GuardedClient, PilotStopped, append_record, build_sdk_client, now
from experiments.plan_memory_pilot import memory_pilot_plan
from experiments.run_memory_controls import empty_record, execute_trial
from experiments.run_pilot import write_json


def validate_approval(plan, approved_hash, ceiling, *, today=None):
    unsigned = {k: v for k, v in plan.items() if k != "plan_sha256"}
    if plan.get("plan_sha256") != approved_hash or digest(unsigned) != approved_hash:
        raise ValueError("Approved plan hash does not match")
    if plan != memory_pilot_plan():
        raise ValueError("Source or configuration changed; review a fresh plan")
    today = today or date.today()
    age = (today - date.fromisoformat(plan["price_verified_on"])).days
    if not 0 <= age <= plan["approval_max_age_days"] or today >= date.fromisoformat(plan["model_shutdown_on"]):
        raise ValueError("Model/pricing verification expired")
    amount = Decimal(str(ceiling))
    if (not amount.is_finite() or not Decimal(plan["budget"]["conservative_run_reserve_usd"])
            <= amount <= Decimal(plan["budget"]["proposed_spending_ceiling_usd"])):
        raise ValueError("Budget must cover the fixed run and not exceed $9.00")


def run_pilot(output, *, mode="offline", plan=None, approved_hash=None, ceiling="9.00", provider=None, prompt_key=False):
    plan = copy.deepcopy(plan or memory_pilot_plan())
    if mode not in ("offline", "live"):
        raise ValueError("Unknown mode")
    if mode == "live":
        validate_approval(plan, approved_hash, ceiling)
        if provider is not None and getattr(provider, "offline_only", False):
            raise ValueError("Offline stub cannot be passed as a live provider")
    elif provider is not None:
        raise ValueError("Offline rehearsal always uses the built-in stub")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    run_id = uuid.uuid4().hex
    records = []
    for entry in plan["design"]["schedule"]:
        row = empty_record(entry, run_id=run_id, mode=mode)
        row.update(status="unattempted", plan_sha256=plan["plan_sha256"])
        records.append(row)
    manifest = {"run_id": run_id, "mode": mode, "status": "running", "created_at": now(),
                "plan_sha256": plan["plan_sha256"], "planned_trials": len(records),
                "approved_budget_usd": str(ceiling) if mode == "live" else None,
                "approved_plan_sha256": approved_hash if mode == "live" else None,
                "authorization_note": "CLI flags acknowledge approval; they do not grant owner permission."}
    write_json(output / "plan.json", plan)
    write_json(output / "manifest.json", manifest)
    write_json(output / "schedule.json", plan["design"]["schedule"])
    owned_provider = False
    client = None
    try:
        if provider is None:
            provider = build_sdk_client(plan, prompt_key=prompt_key) if mode == "live" else OfflineClient()
            owned_provider = mode == "live"
        with (output / "calls.jsonl").open("x", encoding="utf-8") as ledger, \
             (output / "trials.jsonl").open("x", encoding="utf-8") as trials:
            client = GuardedClient(provider, plan, mode=mode, ceiling=ceiling, ledger=ledger)
            for row in records:
                if not client.halted:
                    client.trial_id = row["trial_id"]
                    execute_trial(row, client)
                append_record(trials, row)
        report = analyze(records, plan)
        write_json(output / "evaluation.json", report)
        counts = {name: sum(r["status"] == name for r in records)
                  for name in ("completed", "invalid", "error", "unattempted")}
        manifest["status"] = "stopped" if client.halted else "completed"
        summary = {"run_id": run_id, "mode": mode, "status": manifest["status"], "counts": counts,
                   "planned": len(records), "attempted": len(records) - counts["unattempted"],
                   "accounting": client.accounting(), "behavioral_metrics": None,
                   "note": "Pipeline counts only. See separate evaluation; offline records are never model evidence."}
        write_json(output / "summary.json", summary)
        write_json(output / "manifest.json", manifest)
        return summary
    except BaseException as error:
        manifest.update(status="interrupted_or_setup_failure", error_type=type(error).__name__)
        write_json(output / "manifest.json", manifest)
        # Keep all planned rows even if private key entry or SDK setup failed.
        if not (output / "trials.jsonl").exists():
            with (output / "trials.jsonl").open("x", encoding="utf-8") as handle:
                for row in records:
                    append_record(handle, row)
        raise
    finally:
        if owned_provider:
            provider.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--approved-plan-sha256")
    parser.add_argument("--approved-budget-usd")
    parser.add_argument("--prompt-key", action="store_true")
    args = parser.parse_args(argv)
    if args.execute and not (args.plan and args.approved_plan_sha256 and args.approved_budget_usd):
        parser.error("Live execution requires the reviewed plan, exact hash and explicit approved budget")
    if not args.execute and any((args.plan, args.approved_plan_sha256, args.approved_budget_usd, args.prompt_key)):
        parser.error("Approval/key flags are only accepted with --execute")
    try:
        result = run_pilot(args.output, mode="live" if args.execute else "offline",
                           plan=json.loads(args.plan.read_text()) if args.plan else None,
                           approved_hash=args.approved_plan_sha256,
                           ceiling=args.approved_budget_usd or "9.00", prompt_key=args.prompt_key)
    except (ValueError, InvalidOperation, OSError, PilotStopped) as error:
        parser.error(f"Run could not complete ({type(error).__name__}); inspect saved status. No automatic retry.")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    sys.exit(main())
