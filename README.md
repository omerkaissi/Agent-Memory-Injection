# Agent Memory Injection

A Python research prototype investigating how conversational instructions can enter an agent's higher-priority context through memory summarization.

**Current status:** the original mechanism has been audited. Controlled offline trials, versioned decision scoring and a bounded live-pilot proposal are implemented or documented. No live-model attack-success rate or mitigation result has been established. Offline outputs are clearly labelled stubs and are not research findings.

## Research question

Under what conditions do lower-trust instructions survive conversation summarization, affect subsequent policy-constrained decisions, and resist mitigation?

The original implementation asks a model to preserve future behavioral instructions, then reinserts its summary as a system message. That is an observable authority-assignment problem. Whether the model retains an injected directive and changes behavior must be measured separately.

## Quick start — no API key or dependencies

Use a separate Python 3.9+ installation. The offline suite was tested with Python 3.9.6. Do not execute the historical virtual environment from the original commit.

    python3 -m unittest discover -s tests -v
    python3 attack_demo.py
    python3 -m experiments.run_trials --output results/offline-smoke --repetitions 2 --order-seed 7

Every output directory must be new; existing results are never overwritten.

The demo retains the eight original inputs, but now runs with an explicit offline stub by default. Importing it does not execute the demo. Importing the agent does not construct an API client.

The original offline runner still rejects --live. A separate bounded pilot runner defaults to offline rehearsal and requires explicit plan/hash/budget flags for live execution. No paid run has been approved or executed. The locked optional SDK environment has been clean-installed and tested with fake HTTP responses; authenticated access remains unverified.

## What the comparisons test

| Scenario | Neutral versus attack | Purpose |
|---|---|---|
| original_direct | Same eight messages except turn six | Keep the final direct-choice instruction in both arms to expose that confound |
| heldout_ambiguous | Fixed scripted history differs at one message; identical later question | Probe whether a summary alone changes a decision under an explicit trusted policy |
| heldout_legitimate | Same controlled memory setup, with a fully specified priority question | Check useful task behavior when the trusted policy permits choosing |

The held-out protocol first summarizes a fixed history, then creates a fresh agent containing only the summary, trusted policy, and held-out query. Original messages and intermediate assistant replies are absent from that responder's context. The attack payload is never repeated in the final query.

Message counts and assistant history are matched. Payload text lengths differ and are not token-matched. The controlled task policy is an experimental addition; it is not evidence that the original base prompt contained such a rule.

## Architecture and trust boundary

~~~mermaid
flowchart TD
    U["Lower-trust conversation"] --> H["Memory buffer"]
    H --> S["Instruction-preserving summarizer"]
    S --> M["System-role summary"]
    P["Trusted task policy"] --> R["Response request"]
    M --> R
    Q["Identical held-out query"] --> R
    R --> O["Recorded response"]
~~~

The legacy system-role reinsertion is intentionally preserved as the vulnerable condition. Source labels, constrained summaries and validation will be evaluated in later defense conditions. They are not implemented or claimed effective here.

## Saved artifacts

Each run creates:
- manifest.json — planned trials, randomized-order seed, source fingerprints and run status.
- trials.jsonl — one record per attempted trial, including errors; configuration, full synthetic requests, memory before/after, responses and timing.
- summary.json — completed/error counts by scenario and arm.

Requested model and returned model are separate fields. Offline calls return offline-stub-v1. Missing token usage is null, not zero. All behavioral metrics are null and evaluated is false in offline mode. The order seed controls scheduling only; it is not a model seed.

Raw provider exception messages are excluded from records. Inputs and model responses are recorded intentionally, so use synthetic data only. This is not a general-purpose personal-data redactor.

## Failure-path reproduction

    python3 -m experiments.run_trials --output results/offline-failure --fail-on-call 1

The command exits with status 1 and retains all six failed attempts. An expected injected failure is a software test, not a research outcome.

## Original evidence and limitations

The original commit is fcdf5c74ed35d71e32113155f44302139cac2848. Its eight-turn script summarizes on turns four and seven. The final input directly asks the agent to choose; that confounds the original claim that injected memory alone caused the behavior.

Memory is a process-local list, not persistent disk storage. The base system string is fixed, but the assembled system context changes. No production tool actions, real-world impact, cross-model generality, long-horizon persistence, CVE, zero-day or published research result is established.

The historical writeup.md is preserved with an explicit status note. Future conclusions require a registered rubric, real model outputs, repeated trials, uncertainty estimates and legitimate-task checks.

## Repository map

- agent.py — original agent mechanics with an injectable client and detached event snapshots.
- attack_demo.py — preserved eight-input demonstration with a main guard.
- experiments/ — controlled scenarios, offline transport and JSONL runner.
- tests/ — contract, isolation, failure, legacy-equivalence and live-call-blocking checks.
- docs/reproduction.md — detailed protocol, expected artifacts and next evidence requirements.
- requirements.txt / requirements-lock.txt — optional tested provider environment; offline work uses the standard library.
- experiments/run_pilot.py — fixed-matrix rehearsal and explicitly gated live execution.
- docs/live-execution.md — setup, exact commands, spending reservations and abort behavior.

The bundled venv is removed from Git tracking; existing local environment files are preserved. Original files remain recoverable from the baseline commit. Ignore rules exclude environments, credentials and generated run artifacts.

## Scoring and the first pilot

[Scoring contract](docs/scoring.md) defines policy violations, attack success, utility, invalid responses, paired comparisons and Wilson intervals before data collection. Semantic instruction persistence requires separate manual annotation and remains unmeasured.

    python3 -m evaluation.score results/offline-smoke/trials.jsonl --output results/offline-smoke/evaluation.json
    python3 -m experiments.plan_pilot

The evaluator refuses to turn offline outputs into behavioral findings. The planner prints a 40-trial, at-most-80-call proposal without accessing a provider. See [pilot settings, budget and stopping rules](docs/pilot.md). The guarded live adapter is implemented and tested with fake HTTP responses; explicit spending approval and private credential setup are still required. The original model family has a documented January 14, 2027 API shutdown; later model comparisons must be recorded explicitly.

Code, documentation and research results advance together in reviewable increments. The first increment establishes a reproducible evaluation protocol; future measured results and mitigation comparisons will be reported with their raw evidence and limitations.

## Related work and research scope

- [AgentPoison](https://arxiv.org/abs/2407.12784)
- [Memory Injection Attacks on LLM Agents via Query-Only Interaction / MINJA](https://arxiv.org/abs/2503.03704)
- [From Untrusted Input to Trusted Memory / MPBench](https://arxiv.org/abs/2606.04329)

These establish relevant prior work; this project does not claim to have discovered memory poisoning. The next contribution to investigate is a controlled comparison of summary authority, instruction retention, downstream violations and utility-preserving defenses.

All tests are limited to this authorized synthetic environment.

## Bounded pilot rehearsal

    python3 -m experiments.run_pilot --output results/pilot-rehearsal

This records 40 offline trials, at most 80 stub calls, a durable call journal and an evaluation with null behavioral metrics. See [live execution and budget safeguards](docs/live-execution.md) for the separate paid-run approval requirements. No real-model finding is implied by SDK integration tests.
