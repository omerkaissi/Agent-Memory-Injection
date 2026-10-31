# Reproduction and evaluation contract

## Environment

Offline code requires Python 3.9+ and the standard library. Python 3.9.6 is the tested interpreter. The historical venv has been removed from Git tracking while preserving existing local files. It contains platform-specific paths and packages; nothing in it was installed or executed.

The optional OpenAI SDK remains pinned to 2.15.0, matching original package metadata. Its full dependency set is pinned in requirements-lock.txt, clean-installed on Python 3.9.6, and tested through an in-memory HTTP transport. The first authorized live pilot subsequently completed 80 calls using this environment; saved results are summarized in README.

## Preserve the baseline

Original commit: fcdf5c74ed35d71e32113155f44302139cac2848.
Original tree: 93c324264b1295d10a2b7ff7021d8ca661035036.

The local checkout was reconstructed from GitHub's complete ZIP and metadata because local git network access was unavailable. All 1,982 blob hashes, the tree and exact original commit hash were verified. git fsck --full passed. No remote ref was modified.

Tests retrieve original source from that commit and compare every request produced by the eight-input demo under identical fake completions. The original base prompt, summary prompt, threshold, summary role and eight input strings remain unchanged.

Deliberate interface changes: imports have no side effects; a client must be supplied explicitly; command-line defaults are offline; terminal memory printing is opt-in; errors retain safe structured metadata instead of raw provider text.

## Test and smoke commands

    python3 -m unittest discover -s tests -v
    python3 attack_demo.py
    python3 -m experiments.run_trials --output results/offline-smoke --repetitions 2 --order-seed 7

Expected smoke totals: 12 attempted records, 12 completed, zero provider calls, no behavioral metrics. These are fixtures/transport completions, not successful attacks.

    python3 -m experiments.run_trials --output results/offline-failure --fail-on-call 1

Expected: six attempted records, six errors, process exit 1. All attempts stay in trials.jsonl. A partial interrupted run keeps manifest status running rather than claiming completion.

    python3 -m experiments.run_trials --live --output results/not-created

Expected: exit 2 before output directory creation. No SDK import, credential lookup or network call.

## Matched controls

For original_direct, only input six differs. Both arms retain the original explicit final instruction. Interpret future differences in that scenario descriptively, since intermediate assistant replies would be generated in a live run.

For heldout_ambiguous and heldout_legitimate, assistant messages are fixed and only one user message differs. The same summarizer prompt and memory role are used. The final task is excluded from summarization. A new responder object receives the summary plus a separately specified trusted policy and identical final question.

No demographic, private or external system data is used. There are no external tools or actions.

## Artifact interpretation

- completed means the software pipeline returned a usable string. It does not mean attack success.
- A trial contains events with detached requests; later mutations cannot silently rewrite those snapshots.
- Call failure type is recorded; raw exception text is suppressed because provider failures can contain sensitive values.
- Summary failure leaves the original memory intact.
- expected_outcome is a predefined task target, not a measured result.
- observed_outcome is a literal offline placeholder in this checkpoint.
- evaluated=false and null success/persistence/utility metrics prevent mock outputs from becoming experimental claims.
- Source hashes identify local uncommitted changes as well as the baseline commit.
- Randomization seed controls condition order. It does not control provider sampling.
- Token usage is unknown for stubs, represented as null; incurred API cost is zero because no provider calls occur.
- The injected and neutral messages differ in text length; message counts, not tokens, are matched.

## Deferred live stage

The [scoring rubric](scoring.md) and [pilot proposal](pilot.md) now specify the model/provider, generation parameters, matrix, retries/timeouts, limits and cost calculation. The planner remains offline. A separate gated pilot runner, reservation guard and clean SDK environment are implemented and verified with fakes. Obtain explicit spending approval and configure a private API key before collection; follow live-execution.md. Recheck current availability/pricing if execution occurs later.

Planned metrics: summary directive persistence; trusted-policy violations; legitimate-task success; failed/invalid attempts; cost and latency. Use actual denominators and uncertainty intervals. Do not treat a missing trigger word as semantic removal, or malformed JSON as an automatically safe result.

Then implement isolated defense switches: memory-role/provenance separation, constrained summaries and validation. Compare each against the same attack and benign tasks. No defense efficacy is claimed in this checkpoint.

## Credential scan boundary

A five-rule heuristic scan examined all 1,982 tracked blobs at the one reachable commit and returned no candidates. The observed repository has one branch and zero tags. Deleted/unreachable history and external copies are excluded; pattern scans cannot guarantee the absence of secrets. No credential validity checks were performed.

## Saved first-pilot analysis

The owner executed the first approved live pilot on October 30, 2026. It is complete; do not rerun the old command under its consumed approval. Keep results/pilot-live-001 unchanged. Use evaluation.score or evaluation.audit_pilot with new output paths for offline reanalysis. The raw dataset is preserved separately and is not yet part of the public repository. The schema/audit tests use synthetic fixtures; they do not count as additional empirical trials. See README for measured outcomes and limits.
