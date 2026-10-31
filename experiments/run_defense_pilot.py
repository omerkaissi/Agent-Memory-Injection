"""Defense comparison. Offline by default; a new exact approval is required live."""
import argparse
import copy
from datetime import date
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from types import SimpleNamespace
import uuid

from agent import digest
from evaluation.score_defense import analyze
from experiments.defense_study import make_plan, execute, VERSION
from experiments.structured_memory import EXTRACTION_PROMPT
from experiments.offline import OfflineClient
from experiments.pilot_transport import GuardedClient, PilotStopped, append_record, build_sdk_client, now
from experiments.run_pilot import write_json


class DefenseStub(OfflineClient):
    def create(self, **request):
        response = super().create(**request)
        if request["messages"][0]["content"].startswith(EXTRACTION_PROMPT):
            response.choices[0].message.content = '{"facts":[]}'
        return response


def validate_approval(plan, approved_hash, ceiling, today=None):
    if plan.get("plan_sha256") != approved_hash or plan != make_plan():
        raise ValueError("Approval must match the exact current defense plan/source")
    today = today or date.today()
    age = (today - date.fromisoformat(plan["price_verified_on"])).days
    if not 0 <= age <= 7 or today >= date.fromisoformat(plan["model_shutdown_on"]):
        raise ValueError("Refresh model and pricing verification")
    amount = Decimal(str(ceiling))
    if (not amount.is_finite() or not Decimal(plan["budget"]["conservative_run_reserve_usd"])
            <= amount <= Decimal("10.00")):
        raise ValueError("Budget must cover the full reservation and not exceed $10")


def run(output, *, mode="offline", plan=None, approved_hash=None, ceiling="10.00", prompt_key=False,
        provider=None, fail_on_call=None):
    if mode not in ("offline", "live"):
        raise ValueError("Unknown mode")
    plan = copy.deepcopy(plan or make_plan())
    if mode == "live":
        validate_approval(plan, approved_hash, ceiling)
        if fail_on_call is not None or provider is not None and getattr(provider, "offline_only", False):
            raise ValueError("Synthetic data cannot be used for a live run")
    elif provider is not None or prompt_key or approved_hash:
        raise ValueError("Offline mode uses only the built-in stub and no credentials")
    elif plan != make_plan():
        raise ValueError("Offline rehearsal requires current source/plan")
    if fail_on_call is not None and (type(fail_on_call) is not int or fail_on_call < 1):
        raise ValueError("Failure index must be a positive integer")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    run_id = uuid.uuid4().hex
    records = [{**entry, "schema_version": VERSION, "run_id": run_id, "mode": mode,
                "plan_sha256": plan["plan_sha256"], "status": "unattempted", "error_type": None,
                "events": [], "raw_memory": None, "validated_memory": None,
                "validation_rejected": None, "responder_initial_memory": None,
                "observed_outcome": None, "provider_calls": 0, "stub_calls": 0}
               for entry in plan["schedule"]]
    manifest = {"run_id": run_id, "mode": mode, "status": "running", "created_at": now(),
                "plan_sha256": plan["plan_sha256"], "approved_plan_sha256": approved_hash,
                "approved_budget_usd": ceiling if mode == "live" else None,
                "failure_injection": fail_on_call,
                "authorization_note": "Flags acknowledge separate owner approval; they never grant it."}
    write_json(output / "plan.json", plan)
    write_json(output / "manifest.json", manifest)
    owned = False
    try:
        if provider is None:
            provider = build_sdk_client(plan, prompt_key=prompt_key) if mode == "live" else DefenseStub(fail_on_call)
            owned = mode == "live"
        with (output / "calls.jsonl").open("x") as ledger, (output / "trials.jsonl").open("x") as trials:
            client = GuardedClient(provider, plan, mode=mode, ceiling=ceiling, ledger=ledger)
            for row in records:
                if not client.halted:
                    client.trial_id = row["trial_id"]
                    execute(row, client)
                append_record(trials, row)
        write_json(output / "evaluation.json", analyze(records, plan))
        manifest["status"] = "stopped" if client.halted else "completed"
        summary = {"run_id": run_id, "mode": mode, "status": manifest["status"],
                   "counts": {s: sum(r["status"] == s for r in records)
                              for s in ("completed", "invalid", "error", "unattempted")},
                   "planned_trials": len(records), "accounting": client.accounting(),
                   "behavioral_metrics": None, "note": "Score separately; stubs are software evidence only."}
        write_json(output / "summary.json", summary)
        write_json(output / "manifest.json", manifest)
        return summary
    except BaseException as error:
        manifest.update(status="interrupted_or_setup_failure", error_type=type(error).__name__)
        write_json(output / "manifest.json", manifest)
        # A distinct recovery ledger preserves scheduled rows even after an interrupted write.
        write_json(output / "recovery-ledger.json", records)
        raise
    finally:
        if owned:
            provider.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", type=Path)
    p.add_argument("--print-plan", action="store_true")
    p.add_argument("--execute", action="store_true")
    p.add_argument("--plan", type=Path)
    p.add_argument("--approved-plan-sha256")
    p.add_argument("--approved-budget-usd")
    p.add_argument("--prompt-key", action="store_true")
    p.add_argument("--fail-on-call", type=int)
    args = p.parse_args()
    if args.print_plan:
        if any((args.execute, args.plan, args.output, args.approved_plan_sha256, args.approved_budget_usd, args.prompt_key, args.fail_on_call)):
            p.error("Print-plan cannot be combined with execution options")
        print(json.dumps(make_plan(), indent=2))
        return 0
    if not args.output:
        p.error("An unused output directory is required")
    if args.execute and not (args.plan and args.approved_plan_sha256 and args.approved_budget_usd):
        p.error("Live execution requires a new plan, exact hash and explicit budget")
    if not args.execute and any((args.plan, args.approved_plan_sha256, args.approved_budget_usd, args.prompt_key)):
        p.error("Approval/key options require --execute")
    try:
        result = run(args.output, mode="live" if args.execute else "offline",
                     plan=json.loads(args.plan.read_text()) if args.plan else None,
                     approved_hash=args.approved_plan_sha256, ceiling=args.approved_budget_usd or "10.00",
                     prompt_key=args.prompt_key, fail_on_call=args.fail_on_call)
    except (ValueError, InvalidOperation, OSError, PilotStopped) as error:
        p.error(f"Run stopped ({type(error).__name__}); inspect saved status. Do not automatically retry.")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
