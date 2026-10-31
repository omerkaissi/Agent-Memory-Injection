# Bounded pilot execution

Status: runner implemented locally and tested offline, including the real OpenAI SDK with in-memory HTTP responses. No authenticated model call or paid experiment has been executed. Public publication of this increment remains subject to review. This is an exploratory pilot, not a benchmark of general security.

## Rehearse safely

The default requires Python 3.9+ only. It imports no provider SDK, reads no credential, and performs no network operation:

    python3 -m experiments.run_pilot --output results/pilot-rehearsal

This schedules all 40 trials and uses up to 80 stub calls. Every run directory must be new. Offline decision/persistence/utility metrics remain null even when a fake output resembles a correct answer.

## Provider dependency setup

Keep the historical venv untouched. Create a new ignored .venv:

    python3 -m venv .venv
    .venv/bin/python -m pip install -r requirements.txt
    .venv/bin/python -m pip check
    .venv/bin/python -m unittest discover -s tests -v

requirements-lock.txt records the complete tested dependency set. The production client refuses a different installed version rather than silently changing the transport. Python 3.9.6 on macOS arm64 is the tested installation; other platforms/interpreters have not been validated. The base offline suite still works without these packages; SDK-specific checks are skipped when the SDK is absent.

## Freeze and review before any paid call

After finalizing code, documentation and dependencies, generate the plan:

    .venv/bin/python -m experiments.plan_pilot > results/approved-pilot-plan.json

The results directory must already exist (the rehearsal command creates it). Review this file's matrix, model, settings, plan_sha256, source hashes and cost reservation. Obtain explicit owner approval for that plan and a ceiling no greater than $2.00. A source, prompt, dependency-lock, documentation or Git-commit change invalidates the exact plan comparison; regenerate/review before execution. Model/pricing verification expires after seven days and at the model's documented shutdown, whichever comes first.

The program checks the supplied plan hash, recomputes its contents, compares the current plan, and validates the explicit budget before constructing an SDK client or reading OPENAI_API_KEY. The flags are a deliberate acknowledgement mechanism, not an authorization service and not a substitute for the owner's actual permission.

## Only after approval and private credential setup

Either make OPENAI_API_KEY available privately in the local process environment, or add --prompt-key to the command below and enter the key into the hidden prompt in your own interactive terminal. The prompt does not save the key or put it in command history. Never paste it into chat. A noninteractive process refuses to prompt. The runner does not load .env automatically or fetch credentials from other stores. OPENAI_BASE_URL and OPENAI_LOG must be unset; there is no automatic fallback endpoint. A missing key stops setup with zero dispatched calls.

Replace the placeholders below only with the reviewed plan/hash and owner-approved amount:

    .venv/bin/python -m experiments.run_pilot \
      --execute \
      --plan results/approved-pilot-plan.json \
      --approved-plan-sha256 REVIEWED_PLAN_SHA256 \
      --approved-budget-usd 2.00 \
      --output results/pilot-live-001

## Implemented limits

- Fixed gpt-4o-mini-2024-07-18 snapshot and text-only Chat Completions endpoint; explicit generation settings, store=false, no tools, no streaming, one completion.
- At most 40 trials and 80 calls. No automatic SDK retries, automatic resume, replacement trials or model fallback.
- Before each dispatch, reserve $0.0193536 and fsync a call_reserved record. This covers the published full context plus 256 output tokens at the registered standard rates. Failed calls keep their reservation. Maximum full-run reserve is $1.548288, below the proposed $2.00 ceiling.
- Maximum serialized request size 32,000 bytes and 16 messages. This is a sanity bound, not an exact token counter; the spending reservation uses the full model context instead.
- SDK timeout is 30 seconds per network operation, not a guaranteed 30-second total wall-clock deadline. HTTP redirects and inherited proxy/CA overrides are disabled; standard TLS verification stays enabled.
- Stop the run on a transport error, model mismatch, missing/inconsistent usage, unexpected response shape or journal failure. Retain the attempted error and remaining unattempted schedule separately.
- A truncated/refused summary is an invalid trial and skips the downstream call. Malformed/truncated/refused downstream outputs remain invalid observations; they are not repaired or replaced. These outcomes do not expand sampling.
- Partial outputs from a killed process are never treated as a completed run. Use the pre-call journal to identify requests whose outcome is unknown; do not rerun them automatically.

These are application-level reservations at registered prices, not an account-wide billing cap. Known usage is priced conservatively without caching discounts. Unknown usage stays unknown; a partial known-cost subtotal is not reported as a complete cost total.

## Artifacts and interpretation

plan.json and schedule.json are saved before client setup. manifest.json records mode, runtime and status. calls.jsonl records reservations and responses, including failures, before/after each SDK call; it never includes authorization headers or raw provider exception strings. trials.jsonl contains one row per scheduled trial on normal completion or a handled provider abort. summary.json reports pipeline counts and accounting. evaluation.json applies task-policy-v1.1 to completed/invalid/failed attempts and excludes unattempted trials from attempt denominators.

On process termination or a disk failure, the journals may be partial and evaluation may be absent. Do not manufacture missing responses or treat reserved calls without terminal records as free. Preserve the failed run for investigation.

All recorded prompts and outputs are synthetic, but they are intentionally stored in full. Review logs before any public release. Semantic persistence still requires the separate manual rubric; no automatic keyword score is used.

SDK retry and timeout behavior was checked against the [official v2.15.0 README](https://github.com/openai/openai-python/blob/v2.15.0/README.md). Model rates and availability sources are in [pilot.md](pilot.md).
