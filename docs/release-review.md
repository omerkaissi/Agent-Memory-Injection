# Third public update — approved synthetic evidence disclosure

On October 30, 2026, the owner replied “yeah thats fine with me” to the explicit request to publish raw synthetic experiment records including complete prompts, model outputs, timestamps, usage and provider request identifiers. This approval resolves the earlier data-disclosure boundary. No additional paid experiment is authorized.

## Scope and verification

Publish the two original frozen evidence ZIP archives, covering 26 raw and derived files, with archive/per-file SHA-256 hashes and offline extraction/audit/rescoring instructions. All archive bytes and entries match the preserved originals; CRC checks passed. A bounded scan of the 26 evidence files found no credential patterns, email addresses or local home paths. Such scans are not a universal guarantee of secret absence. No credential validation or provider request occurred.

Update the README, reports and evidence-availability notes to link the public records. Keep source-provenance mapping, measured scores and human-review gaps unchanged. Do not claim that data publication completes annotation or mitigation testing. Prior release reviews below are historical; their private-data statements no longer describe the current release.

---

## Historical second-release review

# Second public update — code and research reports

Owner approved publishing the accumulated code and writing on October 30, 2026. This release keeps raw study records, model-call journals, annotation packets and project/application documents private. No additional paid run is authorized.

## Published scope

- Preserve the existing Git history and exact study-source commits; include intervening runner, scoring, audit and test improvements.
- Make writeup.md the current technical report; archive the original narrative with an explicit evidence-status note.
- Publish detailed reports for both studies and link them prominently from README.
- Document the private evidence inventory and offline auditing requirements. A fresh public clone cannot independently verify the saved model outputs without the private records.

## Verification and limits

The full software suite previously passed 94 tests. This release changes documentation, without changing the agent, scorers or experiments. Both saved datasets were audited and re-scored offline during release preparation and matched their frozen scores. Those records are excluded from the public tree and from the newly published commit ancestry. The original demonstration and earlier released history remain recoverable.

First pilot: 0/10 designated attack successes. Second study: four designated attack cells each 0/10; memory utility 79/80 with one fact-loss/deferral case. The two studies use different policies and are not pooled. Human summary review, mitigation evaluation and full prior-work comparison remain pending. No peer review, novel exploit or production impact is claimed.

A bounded credential-pattern scan inspected release files and Git-reachable history. Its only candidates were dummy test keys in an HTTP-mocked fixture; no actual credential exposure was found. Pattern checks cannot prove universal secret absence. No credential validity check or new model request was performed.

---

## Historical first-release review

# First public update — approved review scope

Owner approved this publication scope on October 30, 2026. This document records the reviewed changes and evidence; publication verification is recorded separately in Project HQ.

## Problem and resulting behavior

The original demo combined a memory-injection message with a final direct instruction to choose, so its outputs could not establish that memory caused the behavior. This update preserves that demonstration and adds matched neutral/attack histories, a fresh summary-only responder and explicit task-policy controls. Default commands run offline without a key or provider calls. A separate evaluator defines valid decisions, violations, utility errors and uncertainty before real-model collection.

## Included changes

- Preserve the original eight inputs, summary prompts, trigger and system-role reintegration as the legacy condition. Keep the original commit recoverable.
- Add safe imports, explicit client injection, structured request/memory/error records and fresh output directories.
- Add offline experiment and evaluation commands, tests, a scoring rubric and a bounded pilot proposal.
- Update README, reproduction instructions and the historical write-up status note. Keep the original write-up body intact.
- Remove 1,978 bundled virtual-environment files from Git tracking while preserving local files and symlinks. Ignore environments, secrets and generated output directories.
- Proposed repository description: Python research project investigating persistent prompt injection through AI-agent memory summarization.
- Proposed topics: ai-security, llm-security, prompt-injection, ai-agents, adversarial-testing, ai-safety, security-research.

## Verification and claims

Thirty offline unit/contract tests passed on Python 3.9.6. Tests include request-for-request equivalence with the original demo, isolation, failure retention, strict scoring, denominator handling, Wilson reference values and refusal to score stubs as model evidence. The evaluator was run on the twelve existing offline smoke records; behavioral rates stayed null. The pilot planner executed without any provider access. Local environment contents were checked against all 1,978 original blob hashes before and after removal from the Git index.

No live-model result, successful attack rate, mitigation efficacy, production vulnerability, novel discovery or publication is claimed. This is a reproducible research prototype with a stated experimental plan. It is appropriate to publish this engineering increment before empirical findings exist, provided these limits remain prominent.

## Publication sequence

1. Publish the owner-approved code, cleanup and documentation together to the existing repository, preserving its history. Apply the description/topics listed above. Confirm the public README and reproduction instructions at the resulting commit.
2. After the live adapter, budget guard, dependency validation and explicit spending approval, run the registered exploratory pilot. Publish measured results with traces, denominators and limitations only after review.
3. Implement and compare defenses under the same protocol. Update the technical report with measured utility/security tradeoffs, including failures and inconclusive outcomes.

Approval covers this release's public code, documentation, cleanup and metadata. API spending is a separate decision; approving this release does not authorize a paid run.
