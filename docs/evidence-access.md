# Evidence availability and offline auditing

The first two synthetic experiment records are public with explicit owner approval, including prompts, model outputs, timestamps, usage and provider request identifiers. Their two frozen ZIP archives and 26 raw/derived files remain unchanged. The new defense bundle is included in this release with the owner's explicit approval of its code, reports and complete synthetic evidence.

The [evidence index](../data/README.md) provides archive/per-file SHA-256 hashes and exact extraction, audit and re-scoring instructions. All reanalysis uses Python 3.9+ without an API key or paid call. Original run folders are unchanged; extraction uses fresh output directories.

The three studies respectively completed 40 trials / 80 calls, 300 trials / 420 calls, and 240 trials / 480 calls. They have separate designs and must not be pooled as a single condition. The defense bundle additionally preserves the 44-file executed source/test snapshot and the 108-test verification log. Audits establish internal consistency, not independently authenticated provider records or account billing verification.

Omer reports completing the earlier human review. Item-level labels for the first two studies' 11 and 35 unique summary texts remain unreconciled in the retained packets. Formal semantic persistence/fidelity rates stay unknown, with 80 unassessed memory-dependent summary policy outcomes in study two. Study three separately retains 80 unassessed free-text policy outcomes. Mechanically checked structured facts and AI observations are not independent human validation. See [review status](review-status.md).

The defense preserved measured utility but did not establish security benefit against a zero-success baseline. No further paid experiment is planned for the agreed upgrade. See the [main report](../writeup.md), [defense report](reports/defense-results.md) and [source mapping](source-provenance.md).
