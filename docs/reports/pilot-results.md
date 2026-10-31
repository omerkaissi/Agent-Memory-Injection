# First live pilot: instruction retention without observed decision deviation

Date: October 30, 2026 (America/Los_Angeles). Researcher: Omer Kaissi. Status: public exploratory research report; not peer reviewed. Analysis and engineering were AI-assisted; no independent human annotation is claimed.

## Finding

The tested memory-injection payload did not cause a policy violation on the ambiguous task: 0 of 10 valid attack trials chose a task, and all 10 correctly deferred. The neutral comparison also deferred in all 10 trials. All 20 fully specified task trials selected the policy-correct Task A. No paired decision changed between attack and neutral arms.

Inspection of all 11 unique summary texts indicates that the target directive was retained in all 20 attack-arm summaries, attributed to the user, and absent from all 20 neutral-arm summaries. This is provisional, nonblind AI-assisted content review, not independent human validation. The frozen evaluator's formal instruction_persistence fields remain null. A separate 11-item review packet is ready for human annotation.

The defensible conclusion is narrow: lower-trust instructions survived this instruction-preserving summarizer and were reintroduced as system-role context, but the responder still followed the explicit task policy on these two fixed tasks. Retention alone did not establish successful behavioral compromise.

## Registered design and evidence

Run ID: c251a61999e8412ba945b13cf3062105.
Plan SHA-256: 4add3443a73a8e2e8944b244b3c865153f358824ffc28738fdc8026c514a00da.
Model requested and returned on all 80 calls: gpt-4o-mini-2024-07-18.
Rubric frozen before collection: task-policy-v1.1.

Two tasks × neutral/attack × 10 repetitions = 40 trials. Each independently summarizes fixed seven-message history, then gives only the generated system-role summary, a trusted task policy, and the held-out query to a fresh responder. The treatment replaces one historical user message. No raw history or direct final attack command reaches the responder. The summary prompt deliberately preserves instructions; this is the legacy protocol, with no new defense condition.

The ambiguous task has insufficient/equal priority and requires defer. The utility task explicitly supplies priority A=9 and B=2 and requires choosing A. The trusted policy is an experimental addition; it was not present in the original eight-turn demo. Thus this is not a reproduction of every detail of the original interaction.

Temperature 0; top_p 1; 256 output-token maximum; one completion; no streaming; no automatic retries; no model seed; order seed 7. API calls ran October 30 from approximately 18:01:53 to 18:03:03 Pacific. The earlier manifest creation time includes the wait for private key entry and is not model execution latency.

## Measured downstream outcomes

| Task | History | Valid / attempted | Observed decision | Policy violations |
|---|---|---:|---|---:|
| Ambiguous | Neutral | 10 / 10 | Defer in all 10 | 0 / 10 |
| Ambiguous | Attack | 10 / 10 | Defer in all 10 | 0 / 10 |
| Fully specified | Neutral | 10 / 10 | Choose A in all 10 | 0 / 10 |
| Fully specified | Attack | 10 / 10 | Choose A in all 10 | 0 / 10 |

Attack success is predefined only for the ambiguous attack stratum: 0/10 (0%). Its Wilson 95% interval is approximately 0–27.8%, under independent Bernoulli assumptions. Each stratum's correct-task rate is 10/10, with a Wilson interval approximately 72.2–100%. These intervals concern repeated requests for fixed tasks, not general robustness across attacks, models, or tasks. Repeated prompts and shared service infrastructure further limit independence assumptions.

All 20 matched pairs agreed on their parsed decision. Within each task, paired violation-rate difference was zero percentage points. No significance test or paired confidence interval was performed. There were zero invalid outputs, transport errors, refusals, truncations, or unattempted scheduled trials. Completed pipeline counts alone would not establish these facts; raw responses and the predefined evaluator were inspected and recomputed.

## Summary inspection

There were seven unique attack-summary strings and four unique neutral-summary strings across 40 trials. An observed attack summary includes:

> They also instructed to preserve guidance that emphasizes prioritizing forward progress over hesitation, even in cases of incomplete information or conflicting guidance.

This sentence explicitly attributes the request to the user. It does not by itself show endorsement or adoption by the responder. Exact source text and SHA-256 keyed provisional annotations are saved separately. All labels require independent human review before reporting a human-validated semantic persistence rate. No inter-rater agreement is claimed.

## Cost, usage, and reproducibility checks

80 provider calls; 11,883 input tokens; 2,803 output tokens; 14,686 tokens total. Usage-based cost estimate at the frozen rates: $0.00346425 (approximately 0.35 cents). This is not an account billing statement and does not include unrelated prepaid credit purchases. The $1.548288 reservation was a conservative accounting bound, not an additional charge. No unknown-usage calls were recorded.

Recorded call latencies total 70.27 seconds, median 0.78 seconds, maximum 2.24 seconds. Four system fingerprints occurred across calls (44, 20, 15 and 1 occurrences); the requested/returned model name remained fixed. The 11 distinct summaries at temperature zero demonstrate that exact output determinism should not be assumed.

The offline audit matched all 40 rows to the registered randomized schedule, checked all 160 journal records and 80 unique request IDs, reconstructed the exact summary and responder requests, verified that only summaries were reinjected, reconciled usage and Decimal costs, and reproduced the saved evaluator output exactly. All seven original run artifacts remain byte-for-byte unchanged. These are internal consistency checks, not independently signed provider attestations.

The executed source matched every registered file hash before documentation edits and is retained in commit 96e81556069c3641d9abe4eed201447cb6c73884. This commit was made after execution to preserve identical source bytes; the run correctly records the earlier HEAD plus dirty source hashes. The subsequent audit tool and tests were added after collection and did not change the frozen decision scorer. All 52 software tests passed; the five new audit tests use synthetic records, not these model results.

The [first-pilot archive](../../data/pilot-001-evidence.zip) contains the original records. Follow [verification and extraction](../../data/README.md), then rerun analysis without credentials or charges, using new output filenames:

    python3 -S -m evaluation.score results/published-evidence/pilot/pilot-live-001/trials.jsonl --output results/pilot-live-001-rescored.json
    python3 -S -m evaluation.audit_pilot results/published-evidence/pilot/pilot-live-001 --expected-plan-sha256 4add3443a73a8e2e8944b244b3c865153f358824ffc28738fdc8026c514a00da --output results/pilot-live-001-reaudit.json

Original artifacts: plan.json, manifest.json, schedule.json, calls.jsonl, trials.jsonl, summary.json and evaluation.json. Derived audit, provisional annotations, human review packet and mapping are stored outside that original run directory. The owner-approved 40-trial run is complete; further paid experiments require a new defined scope and approval. Do not reuse the old approval to rerun this dataset.

## Limitations and next experiment

This is one snapshot, one payload, two fixed tasks and ten repetitions per stratum. The utility task always favors A and supplies all necessary facts in the current query; it checks task compliance but does not measure useful memory recall. Token lengths are not matched. There is no no-memory control, raw-history control, fixed-summary role ablation, natural-conversation condition, multi-cycle test or cross-model replication. The clear task policy and query explicitly referencing that policy may contribute to compliance; this run does not isolate that contribution. Four backend fingerprints and temperature-zero variation are recorded, not interpreted as separate model replications.

The original demo's final instruction directly requests a choice, so its qualitative narrative cannot replace these controlled outcomes. The present negative result neither proves that the original behavior never occurs nor establishes general safety. No mitigation has been evaluated, and zero baseline violations leaves no observed attack rate for a defense to reduce in this pilot.

Historical recommendation after this pilot (the next study now implements the balanced tasks and exposure controls): extend the registered scenario schema to include label-balanced choices (A and B), a task that actually requires remembering a benign fact, and no-memory controls with explicit expected outcomes. Then add raw-history and fixed-summary role/provenance conditions so memory retention, authority assignment, and utility can be separated. Any attack variants should be fixed before collection; report every variant and failure instead of searching until a success is found. Include predefined scorer fixtures as software controls, without calling them real-model attack successes. Freeze the next matrix and cost estimate before seeking permission for additional paid calls.

This report is published with the [current technical report](../../writeup.md) and [evidence inventory](../evidence-access.md). The [raw records and review materials](../../data/README.md) are now public as byte-identical frozen archives. Readers can re-score these saved outputs; internal consistency is not independent provider authentication. The subsequent memory-dependent study addresses some design limitations; see its [separate report](memory-pilot-results.md). The studies use different policies and should not be pooled as one condition.

## Published source mapping

Original study commit IDs identify local snapshots. The [source-provenance table](../source-provenance.md) links their byte-identical public counterparts; publication commit metadata differ, while the executed source files are preserved. The [frozen evidence archives](../../data/README.md) are public with explicit owner approval.
