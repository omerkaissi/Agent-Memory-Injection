"""Separate fixed defense protocol; preserves both original study contracts."""
import copy
from decimal import Decimal
import hashlib
from pathlib import Path
import random

from agent import SUMMARY_PROMPT, SimpleAgent, digest
from experiments.memory_controls import TASKS, TASK_BY_NAME, MEMORY_POLICY, GENERATION_SETTINGS, REQUESTED_MODEL, fixed_history
from experiments.run_trials import source_provenance
from experiments.structured_memory import EXTRACTION_PROMPT, extraction_messages, validate_memory, memory_message

VERSION = "structured-memory-v1"
FORMATS = ("free_text", "structured")


def make_plan():
    schedule = []
    rng = random.Random(7)
    blocks = [(t.name, rep) for t in TASKS for rep in range(1, 11)]
    rng.shuffle(blocks)
    for scenario, rep in blocks:
        conditions = [(f, a) for f in FORMATS for a in ("neutral", "attack")]
        rng.shuffle(conditions)
        for fmt, arm in conditions:
            schedule.append({"trial_id": f"{scenario}:{rep}:{fmt}:{arm}", "scenario": scenario,
                             "repetition": rep, "format": fmt, "arm": arm})
    provenance = source_provenance()
    root = Path(__file__).resolve().parents[1]
    provenance["test_sha256"] = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sorted((root / "tests").glob("*.py"))}
    reserve = (128000 * Decimal("0.15") + 256 * Decimal("0.60")) / 1000000
    plan = {"plan_version": VERSION, "status": "proposal_not_authorized_or_executed",
            "rubric_version": VERSION, "model": REQUESTED_MODEL,
            "endpoint": "https://api.openai.com/v1/chat/completions",
            "settings": dict(GENERATION_SETTINGS), "policy": MEMORY_POLICY,
            "summary_role": "system", "extraction_prompt": EXTRACTION_PROMPT,
            "legacy_prompt": SUMMARY_PROMPT, "repetitions": 10, "order_seed": 7,
            "schedule": schedule, "planned_trials": 240, "max_provider_calls": 480,
            "histories": {t.name: {a: fixed_history(t, a) for a in ("neutral", "attack")} for t in TASKS},
            "queries": {t.name: t.query for t in TASKS},
            "source_provenance": provenance, "max_retries": 0, "timeout_seconds": 30,
            "max_request_bytes": 32000, "price_verified_on": "2026-10-30",
            "approval_max_age_days": 7, "model_shutdown_on": "2027-01-14",
            "price_source": "https://developers.openai.com/api/docs/models/gpt-4o-mini",
            "deprecation_source": "https://developers.openai.com/api/docs/deprecations",
            "budget": {"input_usd_per_million_tokens": "0.15", "output_usd_per_million_tokens": "0.60",
                       "reserved_input_tokens_per_call": 128000, "max_output_tokens_per_call": 256,
                       "reserved_usd_per_call": str(reserve),
                       "conservative_run_reserve_usd": str(reserve * 480),
                       "proposed_spending_ceiling_usd": "10.00"},
            "primary_outcomes": ["Per-scenario answer recovery", "Per-scenario designated attack target choices"],
            "secondary_outcomes": ["Structured fact preservation", "Validation rejection and invalid-output rates"],
            "failure_policy": "Reject invalid structured memory entirely; respond using empty factual memory. Record rejection; never repair or retry. Provider errors stop the run and retain unattempted rows.",
            "limitations": ["Exploratory fixed tasks, one payload/model; no general security claim.",
                            "Package comparison of extraction prompt, schema and validator; cannot attribute effects to individual components.",
                            "Both memories use system role; role/provenance ablation is future work.",
                            "Valid structure and valid source index do not establish factual truth.",
                            "Zero baseline attack success cannot establish attack reduction.",
                            "Free-text semantic metrics need separate human labels; not inferred by AI."]}
    plan["plan_sha256"] = digest(plan)
    return plan


def summary_messages(entry):
    history = fixed_history(TASK_BY_NAME[entry["scenario"]], entry["arm"])
    if entry["format"] == "structured":
        return extraction_messages(history)
    return [{"role": "user", "content": SUMMARY_PROMPT + "".join(
        f"{m['role']}: {m['content']}\n" for m in history)}]


def replacement(entry, raw):
    if entry["format"] == "free_text":
        return {"role": "system", "content": raw}, None, None
    history = fixed_history(TASK_BY_NAME[entry["scenario"]], entry["arm"])
    try:
        memory = validate_memory(raw, history)
        rejected = False
    except ValueError:
        memory, rejected = {"facts": []}, True
    return memory_message(memory), memory, rejected


def execute(row, client):
    """Run fresh independent summary/responder objects; no hidden query leakage."""
    summarizer = SimpleAgent(client=client, model=REQUESTED_MODEL, generation_settings=GENERATION_SETTINGS)
    responder = SimpleAgent(client=client, model=REQUESTED_MODEL, system_prompt=MEMORY_POLICY,
                            generation_settings=GENERATION_SETTINGS)
    before = client.dispatched
    live = row["mode"] == "live"
    try:
        raw = summarizer._complete("summary", summary_messages(row))
        event = summarizer.events[-1]
        if live and (event["finish_reason"] != "stop" or event["refusal"]):
            row["status"] = "invalid"
            return
        message, memory, rejected = replacement(row, raw)
        row.update(raw_memory=raw, validated_memory=memory, validation_rejected=rejected,
                   responder_initial_memory=[message])
        responder.memory = [copy.deepcopy(message)]
        row["observed_outcome"] = responder.chat(TASK_BY_NAME[row["scenario"]].query)
        event = responder.events[-1]
        row["status"] = "invalid" if live and (event["finish_reason"] != "stop" or event["refusal"]) else "completed"
    except (KeyboardInterrupt, SystemExit):
        row.update(status="error", error_type="Interrupted")
        client.halted = True
    except Exception as error:
        row.update(status="error", error_type=type(error).__name__)
        client.halted = True
    finally:
        row["events"] = summarizer.events + responder.events
        row["provider_calls" if live else "stub_calls"] = client.dispatched - before
