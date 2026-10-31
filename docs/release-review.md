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
