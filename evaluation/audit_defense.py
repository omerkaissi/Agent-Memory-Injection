"""Check defense records against the durable per-call journal without API access."""
import argparse
from decimal import Decimal
import json
from pathlib import Path

from agent import digest
from evaluation.score_defense import analyze


def audit(directory):
    root = Path(directory)
    plan = json.loads((root/"plan.json").read_text())
    rows = [json.loads(s) for s in (root/"trials.jsonl").read_text().splitlines()]
    journal = [json.loads(s) for s in (root/"calls.jsonl").read_text().splitlines()]
    report = analyze(rows, plan)
    if report != json.loads((root/"evaluation.json").read_text()):
        raise ValueError("Saved evaluation differs from recomputation")
    if len(journal) % 2:
        raise ValueError("Incomplete call journal; preserve unresolved dispatch")
    expected = [(row, e) for row in rows for e in row["events"]]
    if len(expected) != len(journal)//2:
        raise ValueError("Call journal and event count differ")
    ids, cost = set(), Decimal("0")
    for i, (row, event) in enumerate(expected, 1):
        start, end = journal[2*i-2:2*i]
        if (start["kind"] != "call_reserved" or end["kind"] != "call_result"
                or start["call_number"] != i or end["call_number"] != i
                or start["trial_id"] != row["trial_id"] or end["trial_id"] != row["trial_id"]
                or start["mode"] != row["mode"] or end["mode"] != row["mode"]
                or start["request"] != event["request"]
                or start["request_sha256"] != digest(event["request"])
                or start["request_sha256"] != event["request_sha256"]
                or Decimal(start["reserved_usd"]) != Decimal(plan["budget"]["reserved_usd_per_call"])*i):
            raise ValueError("Call journal mismatch")
        if end["status"] == "completed":
            response = end["response"]
            for key in ("response_text", "returned_model", "usage", "finish_reason", "refusal", "system_fingerprint"):
                if response[key] != event[key]:
                    raise ValueError("Response differs between journal and trace")
            if row["mode"] == "live":
                request_id = response.get("request_id")
                if not request_id or request_id in ids:
                    raise ValueError("Missing or duplicate request ID")
                ids.add(request_id)
                usage = response["usage"]
                actual = (usage["prompt_tokens"]*Decimal(plan["budget"]["input_usd_per_million_tokens"])
                          + usage["completion_tokens"]*Decimal(plan["budget"]["output_usd_per_million_tokens"]))/1000000
                if actual != Decimal(end["usage_cost_estimate_usd"]):
                    raise ValueError("Usage cost mismatch")
                cost += actual
        elif event["status"] != "error":
            raise ValueError("Failure trace mismatch")
    summary = json.loads((root/"summary.json").read_text())
    manifest = json.loads((root/"manifest.json").read_text())
    if (manifest["plan_sha256"] != plan["plan_sha256"] or manifest["run_id"] != rows[0]["run_id"]
            or manifest["mode"] != rows[0]["mode"] or summary["run_id"] != rows[0]["run_id"]
            or summary["mode"] != rows[0]["mode"] or summary["planned_trials"] != len(rows)
            or summary["accounting"]["dispatched_calls"] != len(expected)
            or summary["counts"] != {s: sum(r["status"] == s for r in rows)
                                     for s in ("completed", "invalid", "error", "unattempted")}
            or Decimal(summary["accounting"]["known_usage_cost_estimate_usd"]) != cost):
        raise ValueError("Run totals disagree")
    return {"plan_sha256": plan["plan_sha256"], "mode": rows[0]["mode"], "trials": len(rows),
            "journal_calls": len(expected), "saved_scoring_reproduced": True,
            "note": "Internal consistency only; not independent provider authentication."}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    report = audit(args.run)
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2)


if __name__ == "__main__":
    main()
