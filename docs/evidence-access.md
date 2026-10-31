# Evidence availability and offline auditing

The complete synthetic experiment records are now public with explicit owner approval, including prompts, model outputs, timestamps, usage and provider request identifiers. The [evidence index](../data/README.md) links two byte-identical frozen ZIP archives and a manifest of archive/per-file SHA-256 hashes. The 26 files comprise both raw runs and their separate analysis/review artifacts. No API key or private application material is included.

Follow the [verification, extraction, audit and rescoring instructions](../data/README.md) from a fresh public clone. They use Python 3.9+ and make no API calls. The original local run folders remain unchanged; extraction uses a new output directory.

The first study has 40 trials / 80 recorded calls and the second 300 trials / 420 recorded calls. They have different policies and must not be pooled as one condition. Audits establish internal consistency, not independently authenticated provider records or account billing verification.

Human annotation remains pending for 11 first-pilot and 35 second-study unique summary texts. Formal summary-persistence/fidelity rates remain unknown; 80 memory-dependent summary policy labels also remain unassessed. Provisional AI observations are not independent human validation. A reviewer exposed to outcome reports should disclose that exposure.

This disclosure approval resolves the earlier private-data limitation. It does not authorize additional paid collection or establish mitigation efficacy. See the [main technical report](../writeup.md) and [source mapping](source-provenance.md).
