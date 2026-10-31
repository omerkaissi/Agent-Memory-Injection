# First real-model pilot: registered design and completion

Prepared and executed October 30, 2026 after explicit owner approval. Run c251a61999e8412ba945b13cf3062105 completed 40 trials / 80 calls; estimated usage cost $0.00346425. Ambiguous-task attack success was 0/10; see README results and PILOT_RESULTS.md in Project HQ. The registered settings and conservative reservation below describe the completed run. Further paid runs are not authorized by that completed approval.

## Question and scope

Does replacing neutral historical content with the original progress-over-hesitation directive change a fresh responder's compliance with the explicit task policy after summarization? Test one ambiguous decision and one legitimate priority decision. This is an exploratory mechanism pilot; ten repetitions of a fixed task do not establish robustness, novelty or generality.

| Factor | Proposed value |
|---|---|
| Provider / endpoint | OpenAI Chat Completions, text only |
| Model snapshot | gpt-4o-mini-2024-07-18, for continuity with the original model family |
| Tasks | heldout_ambiguous and heldout_legitimate |
| Arms | neutral / attack, legacy summary as system message |
| Repetitions | 10 matched pairs per task |
| Trials / calls | 40 trials; one summary and one reply each; at most 80 calls |
| Settings | temperature 0, top_p 1, max_completion_tokens 256, n 1, penalties 0, no streaming |
| Seed | 7 for randomized order; no model seed; deterministic outputs not assumed |
| Retries / timeout | No retries; 30 seconds per request |
| Scoring | task-policy-v1.1; no JSON repair or structured-output enforcement |

Keep fixed scripted assistant history and fresh agents. The ambiguous task expects defer; the legitimate task expects A. Token lengths are not matched. Label-balanced tasks, no-memory/raw-memory controls, natural conversations and defense ablations follow under separate registered matrices. The original direct-choice demonstration is not in this paid pilot because it does not answer the primary causal question.

## Current availability and budget proposal

Official [model documentation](https://developers.openai.com/api/docs/models/gpt-4o-mini) lists a 128,000-token context and standard text prices of $0.15 per million input tokens and $0.60 per million output tokens. Checked October 30, 2026. The [deprecation notice](https://developers.openai.com/api/docs/deprecations) schedules API removal on January 14, 2027. Account-level access to the snapshot succeeded for all 80 pilot calls; later availability is not guaranteed. No automatic fallback is permitted; a model change requires a new recorded plan.

Reserve the cost of the entire 128,000-token context for every request plus its 256 output tokens. This is deliberately much larger than these short prompts; it avoids claiming an exact token estimate from character length. Do not subtract cached-input discounts or refund a reservation after a failed call.

    per-call reservation = (128000 × $0.15 + 256 × $0.60) / 1000000
                         = $0.0193536
    maximum 80-call reservation = $1.548288
    proposed owner-approved ceiling = $2.00

These are conservative reservations at published rates, not measured costs or an account-wide billing cap. The reserve covers at most 10,240,000 input and 20,480 output tokens; actual pilot usage was 11,883 input and 2,803 output tokens. The implemented adapter restricts the model/endpoint/settings, counts every attempt, disables SDK retries, reserves budget before dispatch and stops on missing or inconsistent usage. These controls have been tested with fakes and the clean installed SDK. This code's spending limit cannot cap unrelated activity in the provider account.

## Stopping and data handling

Stop on first API/transport error, model mismatch, missing usage or unexpected completion shape. Retain attempts already made; explicitly mark remaining scheduled trials unattempted. Do not rerun or replace failed, malformed or truncated outputs. Normal malformed model decisions remain invalid observations; they do not trigger outcome-based extra sampling.

Before calling the provider, record the frozen plan, source hashes and full schedule. After each call, durably record request/response metadata, usage and reservation. Use only the scripted synthetic data. Read the API key from secure local configuration at execution time; never paste it into chat or commit it. Do not use an inherited alternative API base URL. Redact raw SDK exception text.

## Reviewable dry run

    python3 -m experiments.plan_pilot

This prints the exact matrix, settings, calculation, source hashes and plan hash. It performs no provider calls, SDK import or credential lookup. The live adapter, clean dependency installation and budget-guard tests are complete locally. Explicit cost approval and private credential setup remain prerequisites for any future run; the first approved run is complete.
