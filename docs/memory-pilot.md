# Second live study: memory-pilot-v1

Current status: the owner approved this exact scope with a $9 ceiling and executed it on October 30, 2026. Run `4a87d24725b24432a497a4607f9ac617` completed 300 valid trials / 420 calls, estimated usage cost $0.01752360. Four designated attack cells each had 0/10 target choices; memory utility was 79/80 across exposed-memory conditions. One summary omitted priorities and led to deferral. Human fact/persistence review remains pending. See README for results and limitations. Both pilots' single-run approvals are consumed; no additional paid run is authorized. The original proposal below is preserved as the registered method, not a renewed spending authorization.

## Fixed scope

- Six scenarios from [memory-controls.md](memory-controls.md).
- One no-memory reference plus neutral/attack raw-history and summary trials per scenario/repetition.
- Ten repetitions per scenario: **300 trials, at most 420 provider calls** (60 no-memory replies, 120 raw-history replies, 120 summaries and 120 summary-based replies).
- Original payload only, new factual-memory policy, legacy summary prompt and system-role reinsertion. No defenses, tool actions, external victims or personal data.
- gpt-4o-mini-2024-07-18; temperature 0, top_p 1, max_completion_tokens 256, frequency/presence penalties 0, n 1, stream false, store false. No model seed; order seed 7.
- Scoring frozen as [memory-policy-v1](memory-scoring.md); per-task outcomes, missing-data bounds, human annotation and descriptive comparisons defined before collection.

The model choice keeps the first pilot's snapshot while changing the task/control design. That helps comparison but does not make the two studies identical. Temperature zero does not guarantee deterministic responses. Ten repetitions per cell do not establish broad robustness.

## Price and spending proposal

Official sources checked October 30, 2026 Pacific / October 31 UTC:

- [Model and token pricing](https://developers.openai.com/api/docs/models/gpt-4o-mini): $0.15 per million input tokens, $0.60 per million output tokens, 128,000 context window.
- [Deprecations](https://developers.openai.com/api/docs/deprecations): this snapshot is scheduled to shut down January 14, 2027. Account access is not guaranteed by a documentation check; there is no automatic fallback.

The runner reserves the cost of 128,000 input tokens plus 256 output tokens before each request: $0.0193536 per call. Across 420 calls that is **$8.128512**, rounded up to a proposed **$9.00 spending ceiling**. Total reserved input: 53,760,000 tokens; output cap: 107,520 tokens. The input reservation intentionally exceeds these short prompts' expected usage; it is not a bill or an expected-charge estimate. The first pilot's much smaller actual cost cannot guarantee this study's charge.

This ceiling applies to this runner's one fixed study. It is not an account-wide billing cap. No automatic top-up, retries, replacement trials, caching discounts or refund of a timed-out request's reservation are assumed. Actual usage-based estimates and unknown-usage calls are recorded separately. No additional paid request was made to verify pricing or account access.

## Run protections

The runner reuses the previously tested locked-SDK transport: fixed endpoint, verified TLS, no proxy/CA environment inheritance, no redirects, no SDK retries, 30-second operation timeout, request byte limit, full-context reservation and durable pre-dispatch journal. It refuses altered source/configuration, an incorrect plan hash, a non-finite/insufficient/over-limit budget, stale price verification (older than seven days), or the model shutdown date. A changed source file requires a newly reviewed plan; it is not silently allowed under the previous hash.

Provider/transport/model/usage failures stop the run and preserve failed/unattempted rows. Refused/truncated summaries skip the downstream call. Invalid final decisions remain invalid and are not repaired or replaced. Interruptions are recorded; disk-write failure stops dispatch. A setup/key-entry failure preserves the whole schedule as unattempted. A partial run is not permission to retry. Output directories cannot be reused.

Credentials are entered privately in the existing hidden prompt. Do not put keys in chat, scripts, plan files or committed code. The new runner has no automatic key discovery beyond its explicit local prompt or environment option.

## Rehearse and inspect without charges

```sh
python3 -S -m experiments.plan_memory_pilot
python3 -S -m experiments.run_memory_pilot --output results/memory-pilot-rehearsal
python3 -S -m evaluation.score_memory results/memory-pilot-rehearsal --output results/memory-pilot-rehearsal/reanalysis.json
```

Rehearsal records 300 offline trials, 420 stub calls and an unscored evaluation. Artifacts include plan, manifest, schedule, calls journal, trials, pipeline summary and evaluation. The plan includes exact histories, policy, queries, schedule, settings, scoring version, budget and source fingerprints. The top-level live proposal wraps the unchanged offline matrix definition; its `planned_stub_calls` field describes rehearsal counts, while top-level `max_provider_calls` defines the live cap.

The paid entry point is `experiments.run_memory_pilot --execute`, and it additionally requires `--plan`, `--approved-plan-sha256` and `--approved-budget-usd`. Use `--prompt-key` for private entry. Those flags acknowledge the owner's approval; they do not grant it. The older `experiments.run_memory_controls` remains offline-only, and the original `run_pilot` remains bound to the first study. An exact command is provided only after the owner approves this concrete second-study scope.

## Interpretation and next checkpoint

Retain all outcomes, including zero attack successes, inconsistent behavior, malformed output and failed calls. Inspect utility and attack-goal results before designing defenses. Completing this study cannot establish an isolated role-authority effect because raw/summary conditions change multiple factors. It also cannot establish mitigation efficacy: no defense is included. The later fixed-summary role experiment and human summary review remain separate work.

Local implementation, current offline verification and the exact frozen proposal are reviewable before spending approval. Public code/data publication is a separate scope decision; no publication is part of executing this proposal.
