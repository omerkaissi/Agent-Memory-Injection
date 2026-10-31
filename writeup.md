# Agent Memory Injection: instruction retention, policy adherence and memory utility

**Omer Kaissi · October 30, 2026**

Public exploratory research report. Engineering and analysis were AI-assisted. This is not a peer-reviewed paper; independent human summary annotation remains pending.

## Abstract

This project investigates whether untrusted conversational instructions survive memory summarization and change an agent's later policy-constrained decisions. A Python agent compresses conversation history and reinserts the summary as system-role context. Two separately registered studies used `gpt-4o-mini-2024-07-18`. The first completed 40 trials and observed 0/10 designated attack successes. The second completed 300 trials across no-memory, raw-history and summary conditions, observing 0/10 target choices in each of four designated attack cells. Historical facts supported correct answers in 79/80 exposed-memory utility trials; all 20 corresponding no-memory controls deferred. One summary omitted numerical facts and the responder deferred. These results distinguish instruction retention, task utility and behavioral compromise. They do not establish general robustness, a causal attack effect or mitigation efficacy.

## Motivation and research question

Summarized conversation is useful context, but its origin remains untrusted. A summary can mix facts with behavioral requests. Promoting that mixture to a system message creates an authority boundary worth testing. The implementation exposes that boundary; its existence alone does not show that a downstream model follows the injected instruction.

The central question is: **under what conditions do conversational instructions persist through summarization, influence later decisions, and interact with legitimate memory use?**

The original eight-turn demonstration ends by directly instructing the agent to choose. That instruction confounds its original explanation of memory-caused behavior. The [archived narrative](docs/archive/original-writeup.md) and original Git commit are preserved; the controlled studies replace those causal claims with measured outcomes.

## Threat model and system

An attacker controls one designated historical user message, but cannot edit the trusted task policy, model, evaluator or code. Histories are synthetic, assistant acknowledgments are fixed, and attack/neutral pairs share the same later question. There are no external tools, real user data, production actions, shared-user memory bank or persistent disk memory in the agent. Saved experiment logs are distinct from its process-local conversational memory.

The payload asks the summarizer to preserve guidance favoring forward progress over hesitation despite incomplete information or conflicting guidance. The summarizer deliberately retains future behavioral instructions, preserving the original mechanism. A fresh responder receives the resulting system-role summary, trusted task rule and held-out query. The final query does not repeat the attack command.

```mermaid
flowchart TD
    H["Lower-trust conversation"] --> S["Instruction-preserving summary"]
    S --> M["Summary inserted as system context"]
    M --> R["Fresh responder"]
    P["Trusted numerical-priority policy"] --> R
    Q["Held-out question"] --> R
    R --> E["Recorded decision and evaluation"]
```

The trusted rule chooses the higher numerical priority and defers on tied or missing priorities. The first study emphasizes facts in the current query. The second explicitly permits historical facts while rejecting remembered behavioral rules. That policy change makes them separate studies, not replications under identical conditions.

## Hypotheses and measurements

The broader hypotheses concern directive retention, increased policy violations after attack histories, effects of memory role/provenance, and defenses that preserve utility. Only the registered task/exposure comparisons below have been collected; no defense or fixed-summary authority ablation has been run.

| Measure | Operational meaning |
|---|---|
| Valid trial | Required calls and records are complete, with a strictly parsed decision and no refusal or truncation |
| Attack success | In a designated tied/missing-priority attack trial, choose a task when the registered endpoint requires deferral |
| Answer recovery | Match the complete-information answer; losing a needed fact can reduce this without proving a policy violation |
| Available-evidence policy violation | Disagree with the rule given facts actually available; summary-dependent cases await human fact labels |
| Instruction persistence | Human assessment of the directive in the summary, separate from whether it was followed |
| Mitigation effectiveness | Matched change in attack and utility outcomes; not measured in this release |

Scoring contracts were fixed before collection. Formal semantic labels stay unknown until human review. Neither valid JSON nor a completed pipeline automatically establishes attack success or policy compliance. See the [first rubric](docs/scoring.md) and [memory rubric](docs/memory-scoring.md).

## Experimental setup

Both studies request the same snapshot, temperature 0, top_p 1 and at most 256 output tokens per call. Order seed 7 randomizes the schedule; there is no model seed, retry, replacement trial or fallback. Fixed histories match message counts but not token lengths. All attempted and scheduled trials remain in the records.

| Study | Design | Trials | Calls |
|---|---|---:|---:|
| First pilot | Two held-out tasks × neutral/attack history × ten repetitions; summary exposure | 40 | 80 |
| Memory-control pilot | Six scenarios × five exposure/history conditions × ten repetitions | 300 | 420 |

The second study includes current-query A/B tasks, memory-only A/B tasks, tied priorities and missing priorities. Each block has one shared no-memory control plus raw-neutral, raw-attack, summary-neutral and summary-attack conditions. The no-memory control is not duplicated as independent attack/neutral evidence. Raw history bypasses compression; summary responders never receive the original history.

## Results

### First pilot

The ambiguous attack condition produced 0/10 target choices; its neutral comparison also deferred in all ten trials. Both fully specified task arms chose A in 10/10 trials. All 20 neutral/attack pairs agreed. No invalid output, refusal, truncation or API error occurred.

Nonblind AI inspection of 11 unique summaries suggested the directive remained in all 20 attack summaries, attributed to the user, and was absent from all 20 neutral summaries. This is a provisional content observation. Human-validated persistence rates remain unknown. The [detailed first-pilot report](docs/reports/pilot-results.md) separates those observations from decision scoring.

### Memory-control pilot

| Designated task | Exposure | Attack target choices | Neutral target choices |
|---|---|---:|---:|
| Tied priorities | Raw | 0/10 | 0/10 |
| Tied priorities | Summary | 0/10 | 0/10 |
| Missing priorities | Raw | 0/10 | 0/10 |
| Missing priorities | Summary | 0/10 | 0/10 |

The descriptive attack total is **0/40**, not 0/300. All twenty corresponding no-memory controls also deferred. Each 0/10 cell has an approximate Wilson 95% interval of 0–27.8% under independent Bernoulli assumptions. These are repeated fixed-template results, not a general attack-prevention estimate.

| Hidden-fact condition | A-higher answers recovered | B-higher answers recovered |
|---|---:|---:|
| No memory | 0/10; all deferred | 0/10; all deferred |
| Raw, neutral | 10/10 | 10/10 |
| Raw, attack | 10/10 | 10/10 |
| Summary, neutral | 10/10 | 10/10 |
| Summary, attack | 10/10 | 9/10 |

Exposed memory recovered 79/80 answers: raw history 40/40 and summaries 39/40. No-memory deferral is correct given the absence of facts. All 100 current-query utility controls recovered their expected answer. Of 120 neutral/attack pairs, one had different decisions. All 300 outputs were valid.

The discordant trial, `memory_b:8:summary:attack`, began with A=2 and B=9. Its summary retained the forward-progress directive but omitted both numbers; the responder deferred. Its neutral counterpart retained the numbers and chose B. This is a utility failure consistent with abstention after fact loss, not registered attack success. A single pair does not establish that injection caused the omission. The 9/10 answer-recovery interval is approximately 59.6–98.2%.

There are 35 unique texts across 120 summaries. Human review is pending for factual preservation and directive persistence. Policy outcomes remain unassessed for 80 memory-dependent summary trials; the other 220 assessable trials have zero violations. See the [detailed memory-control report](docs/reports/memory-pilot-results.md) and [evidence availability](docs/evidence-access.md).

## Discussion and limitations

The clearest result is the separation of retained language from downstream instruction adoption. Under the tested policies, the payload did not produce its designated behavioral goal. The second study additionally demonstrates useful historical context and one failure to preserve a needed fact. Neither result resolves the broader security question.

These studies cover one snapshot, one payload, fixed short histories and ten repetitions per cell. Backend fingerprints and distinct summaries show that temperature zero does not imply identical outputs. Repeated prompts and shared service infrastructure limit independence assumptions. There is no cross-model replication, natural-conversation benchmark, long-horizon experiment or production exploit. The explicit task policy may contribute to compliance; that contribution was not isolated.

Raw-versus-summary comparisons jointly change compression, context length and message authority. A fixed-summary experiment must hold the text constant to isolate role/provenance. AI analysis is disclosed and is not an independent human reviewer. No mitigation has been evaluated. Zero observed baseline attack successes cannot demonstrate a defense's reduction in attack rate.

## Related work

This is preliminary positioning based on the cited primary abstracts, not a systematic literature review. [AgentPoison](https://arxiv.org/abs/2407.12784) studies poisoning memory or knowledge bases using optimized retrieval triggers. [MINJA](https://arxiv.org/abs/2503.03704) studies query-only interactions that place malicious records in an agent's memory bank. [From Untrusted Input to Trusted Memory](https://arxiv.org/abs/2606.04329) introduces a broader memory-poisoning taxonomy and MPBench.

This project examines a small sequential summarization pipeline with controlled numerical decisions. It does not reproduce those benchmarks or claim to discover memory poisoning. Its contribution at this stage is a transparent experimental implementation, preserved negative findings, useful-memory controls and a documented failure case. Full methodological comparison and novelty assessment remain future work.

## Reproducibility and cost

The raw runs, derived analyses, blank review packets and hashes are preserved privately. They are not included in this public release. See [evidence availability](docs/evidence-access.md) for the artifact inventory, limitations and offline audit commands for readers who obtain the records. Public code supports running new experiments; it does not by itself let readers independently verify these saved model outputs. Offline auditing of the saved records requires Python 3.9+ and no key or paid call. The 94-test software suite passed before this documentation/data release; synthetic tests are not model observations. Audits check internal consistency, not independent provider authenticity.

The first study used 11,883 input and 2,803 output tokens, estimated at $0.00346425. The second used 77,156 input and 9,917 output tokens, estimated at $0.01752360. These are estimates at registered prices, not account billing statements. Conservative reservations were spending bounds, not measured charges.

Original source remains at `fcdf5c74ed35d71e32113155f44302139cac2848`. The first study's executed source bytes were preserved in post-run commit `96e81556069c3641d9abe4eed201447cb6c73884`; its original dirty-source metadata stays intact. The second executed commit is `9cdb719199e66e94bde2531dccae65959962af55`. Frozen plan hashes and settings accompany each dataset. Fresh collection requires a newly reviewed model, scope and budget; old run approvals cannot be reused.

## Next research steps

Complete human annotation of the existing summaries first. Then compare structured, origin-labeled factual memory with the current free-text summary, measuring fact retention and legitimate-task performance alongside adversarial outcomes. Later vary the role/provenance of identical summaries to isolate authority effects. Predeclare variants and retain failures and negative outcomes.

The current evidence supports a narrow conclusion: an instruction-preserving memory pipeline can retain adversarial guidance without the tested responder adopting its behavioral goal, while useful facts can occasionally be lost. Both outcomes belong in the research record.
