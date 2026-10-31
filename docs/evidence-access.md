# Evidence availability and offline auditing

This public release contains the implementation, scoring and audit tools, synthetic unit-test fixtures, aggregate findings and technical reports. It does not contain the raw live-study records, model-call journals or annotation packets. Those files are preserved privately by the project owner. Public code alone cannot independently verify the reported saved model outputs.

## Preserved artifacts

| Private directory | Contents |
|---|---|
| results/pilot-live-001 | Seven raw files: 40 trials, 80 recorded calls |
| results/memory-live-001 | Seven raw files: 300 trials, 420 recorded calls |
| results/pilot-live-001-analysis | Audit, explicitly provisional AI observations, 11-text blank human review packet and mapping |
| results/memory-live-001-analysis | Audit, scoring, aggregate analysis, nonblind anomaly trace and 35-text blank human review packet |

Each raw directory contains plan.json, manifest.json, schedule.json, calls.jsonl, trials.jsonl, summary.json and evaluation.json. The plans identify model/settings, prompts, randomized schedules and executed source hashes. Original records are not edited by the audit tools. Private evidence archives preserve raw and derived files separately.

## Commands for readers with the original records

These examples assume the privately retained directories have been placed at the paths above. They are not one-command reproduction from a fresh public clone. Output filenames must be new. No API key or paid model call is needed for auditing saved records.

```bash
python3 -S -m evaluation.audit_pilot results/pilot-live-001 --expected-plan-sha256 4add3443a73a8e2e8944b244b3c865153f358824ffc28738fdc8026c514a00da --output results/pilot-rechecked.json
python3 -S -m evaluation.audit_memory results/memory-live-001 --expected-plan-sha256 9500439baf60d5d1681bcf116371715a37299210fcc04c98ca0975ee7162b8d9 --output results/memory-rechecked.json
```

Expected historical totals: 40 trials / 80 calls and 300 trials / 420 calls. These commands make no new requests. Audits establish internal consistency, not independently authenticated provider records or billing verification. See [reproduction](reproduction.md) for offline software exercises available from a public clone, and [live execution](live-execution.md) for the separately gated collection path.

## Human review and disclosure status

Human annotation is pending for both studies. Formal summary persistence/fidelity rates remain unknown; the second study also leaves 80 memory-dependent summary policy labels unassessed. Provisional AI observations are not independent human validation. A reviewer exposed to the outcome reports should disclose that exposure; attack wording can reveal treatment even when metadata are hidden.

Any future public raw-data release needs separate approval for full synthetic prompts, model outputs, usage, timestamps and provider request identifiers. Publication of these reports does not authorize that disclosure or additional paid collection.
