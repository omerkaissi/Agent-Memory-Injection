# Structured factual-memory comparison

Status: the approved live comparison completed 240 valid trials / 480 calls.
Both formats recovered 120/120 reference answers and had 0/20 designated
attack successes; all 120 structured fact sets matched the expected facts.
See the [measured results and limitations](reports/defense-results.md).
The single-run approval is consumed; the code and evidence are included in this owner-approved release.
Omer reports completing the earlier human review; the completed labels have not
yet been located in the checked project files. Preserve that distinction rather
than treating AI labels as human review or asserting the owner did not review.

## Concrete comparison

Six existing tasks × two history arms (neutral/attack) × two memory formats ×
ten repetitions = **240 trials, at most 480 model calls**. Both formats are
collected in this new run, in randomized matched blocks (order seed 7).
Original 40/300-trial runs remain frozen historical evidence, not fresh controls.

The baseline keeps the original instruction-preserving free-text summary. The
defense asks for only A/B numeric priorities with a user-message source index.
The validator rejects unknown fields, arbitrary prose, duplicate keys/tasks,
invalid source references, booleans, nonfinite/out-of-range priorities and
oversized output. It reconstructs canonical JSON containing only allowed
values and a source-role label supplied by code. Source message text never
passes through that schema into the responder.

Rejected structured outputs become empty factual memory, with rejection
recorded. The responder still runs, so lost utility and resulting decisions
remain measured. There is no repair call or retry. Refused/truncated summaries
skip the responder and stay invalid. Provider failures stop collection and keep
all remaining trials as unattempted. Setup interruptions save a recovery ledger.

Both formats retain the **system memory role**, the same trusted task policy,
histories, held-out queries, model snapshot and generation settings. This first
comparison tests the structured extraction/validation package, not role
separation or the independent effect of each package component. A separate
fixed-summary role experiment remains future work; no additional scope is
approved by this document.

## What can and cannot be concluded

Primary endpoints are per-task answer recovery and designated attack target
choices (tied/missing-priority attack arms only). Report per-cell counts,
Wilson intervals, missing-outcome bounds and descriptive matched differences.
Do not use all 240 trials as an attack-success denominator. Invalid, rejected,
failed and unattempted cases remain in the ledger and denominators.

Structured facts can be compared mechanically to the known synthetic source
facts. A valid index is NOT proof that the cited message entails the numeric
claim; incorrect numbers and false attribution are residual risks. Free-text
semantic fact/persistence metrics remain unknown without separate human labels.
Current-query policy checks and structured available-evidence policy checks
are deterministic, and are separate from complete-information answer recovery.
Rejected memory can produce correct deferral but poor answer recovery.

The old baseline observed zero attack-goal successes. A new zero/zero result
cannot demonstrate attack reduction. This small study measures utility and
security outcomes for one fixed payload/model, not general safety. Numeric
schema constraints are task-specific and are not a general memory solution.
The raw output and its validation outcome remain inspectable.

## Rehearse, audit and reproduce without an API key

Use an unused output directory for every execution:

```bash
python3 -S -m experiments.run_defense_pilot --output results/defense-rehearsal
python3 -S -m evaluation.audit_defense results/defense-rehearsal --output results/defense-reaudit.json
python3 -S -m evaluation.score_defense results/defense-rehearsal --output results/defense-rescored.json
python3 -S -m experiments.run_defense_pilot --output results/defense-failure --fail-on-call 3
python3 -S -m experiments.run_defense_pilot --print-plan
```

Rehearsals produce 240 records / 480 simulated calls and no empirical metrics.
The injected failure retains 1 completed, 1 error and 238 unattempted records.
All old source modules and original records are preserved. Audit/re-scoring
checks internal consistency, not independently authenticated provider responses.

## Executed live scope and spending gate

Snapshot: `gpt-4o-mini-2024-07-18`; temperature 0, top_p 1, 256 output tokens,
no model seed, retries, substitutions or automatic reruns. The existing guarded
SDK transport and private key entry are reused. No keys are saved.

Official [pricing](https://developers.openai.com/api/docs/models/gpt-4o-mini)
checked October 30, 2026: $0.15/million input and $0.60/million output tokens.
Reserving the full 128,000-token context per call plus 256 output tokens gives
**$9.289728 maximum reservation** across 480 calls. Approved owner ceiling:
**$10 for this single fixed run**. This deliberately conservative reservation
is not an expected bill. Actual usage is recorded separately. The model is
[scheduled for removal](https://developers.openai.com/api/docs/deprecations)
on January 14, 2027; no replacement model is silently selected.

Live execution requires the saved plan, its exact SHA-256, a budget covering
the reservation within $10, unchanged source/tests, current pricing verification
(at most seven days old), and separate owner authorization. The old study
approval hashes are rejected. CLI flags acknowledge approval; they do not grant
permission. The approved run used plan SHA-256
`857c11056cf4b04804cd8f0a452dd1ba94823d122a73aa270a2b8f868e28ede1`.
Recorded usage was estimated at $0.02132775. This approval cannot be reused.

The full ledger was audited and re-scored offline, all scheduled conditions
were retained, and the report records the zero/zero security limitation. The
owner approved publication of the concrete code, report and synthetic evidence release. The agreed
experimental scope is complete; additional attacks/models/role ablations are
optional future work.
