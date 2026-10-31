"""Print the proposed pilot and conservative budget; never call a provider."""
from decimal import Decimal
import json

from agent import digest
from evaluation.score import RUBRIC_VERSION
from experiments.run_trials import source_provenance
from experiments.scenarios import SCENARIO_BY_NAME, fixed_history


def pilot_plan():
    names = ["heldout_ambiguous", "heldout_legitimate"]
    repetitions = 10
    trials = len(names) * 2 * repetitions
    calls = trials * 2
    # Reserve the entire published context window per call. This deliberately
    # overestimates input instead of pretending a character count is tokenization.
    input_tokens_per_call = 128000
    output_tokens_per_call = 256
    input_rate, output_rate = Decimal("0.15"), Decimal("0.60")
    reserve = (input_tokens_per_call * input_rate + output_tokens_per_call * output_rate) / 1000000
    matrix = [{"scenario": name, "arm": arm, "repetitions": repetitions,
               "expected": SCENARIO_BY_NAME[name].expected,
               "system_prompt": SCENARIO_BY_NAME[name].system_prompt,
               "query": SCENARIO_BY_NAME[name].query,
               "history": fixed_history(arm)} for name in names for arm in ("neutral", "attack")]
    plan = {
        "plan_version": "pilot-v1", "status": "proposal_not_authorized_or_executed",
        "live_execution_implemented": False, "provider": "OpenAI",
        "endpoint": "https://api.openai.com/v1/chat/completions",
        "model": "gpt-4o-mini-2024-07-18",
        "model_status": "Deprecated; documented API shutdown 2027-01-14. Account access unverified.",
        "price_verified_on": "2026-10-30",
        "price_source": "https://developers.openai.com/api/docs/models/gpt-4o-mini",
        "deprecation_source": "https://developers.openai.com/api/docs/deprecations",
        "settings": {"temperature": 0, "top_p": 1, "max_completion_tokens": output_tokens_per_call,
                     "presence_penalty": 0, "frequency_penalty": 0, "n": 1, "stream": False},
        "model_seed": None, "order_seed": 7, "rubric_version": RUBRIC_VERSION,
        "matrix": matrix, "planned_trials": trials, "max_provider_calls": calls,
        "max_retries": 0, "timeout_seconds": 30,
        "budget": {
            "input_usd_per_million_tokens": str(input_rate),
            "output_usd_per_million_tokens": str(output_rate),
            "reserved_input_tokens_per_call": input_tokens_per_call,
            "max_output_tokens_per_call": output_tokens_per_call,
            "total_reserved_input_tokens": calls * input_tokens_per_call,
            "total_output_token_cap": calls * output_tokens_per_call,
            "reserved_usd_per_call": str(reserve),
            "conservative_run_reserve_usd": str((reserve * calls).normalize()),
            "proposed_spending_ceiling_usd": "2.00",
            "note": "Proposal only. Reserve full-context cost before each request, including failed requests; no credit for caching. Guard must be implemented and tested before paid execution.",
        },
        "stopping_rules": [
            "Abort on first transport/API error; retain failed and unattempted entries separately.",
            "Abort on missing usage, model mismatch or unexpected completion shape.",
            "Do not repair, retry or replace malformed/truncated model outputs; retain them for scoring.",
            "Abort before a request would exceed call/token/cost reservations.",
            "No automatic model fallback or extra trials based on observed success.",
        ],
        "limitations": [
            "Exploratory: ten repetitions of each of only two tasks; no generalization or novelty claim.",
            "One payload, legacy summarizer, system-role memory; no mitigation comparison yet.",
            "Utility task always favors A; label-balanced and no-memory controls belong in the next registered matrix.",
            "No structured-output enforcement: JSON compliance is an observed outcome, not an API constraint.",
            "temperature=0 does not guarantee deterministic outputs.",
        ],
        "source_provenance": source_provenance(),
    }
    plan["plan_sha256"] = digest(plan)
    return plan


if __name__ == "__main__":
    print(json.dumps(pilot_plan(), indent=2))
