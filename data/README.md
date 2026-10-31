# Synthetic experiment records and offline reanalysis

The owner approved public disclosure of the first two complete synthetic experiment records: prompts, model outputs, timestamps, usage and provider request identifiers. Those archives also include separate analyses and blank human-review packets. The owner also explicitly approved the third defense bundle, included in this release and described below. No API key or private application material is included.

The ZIP files are byte-identical to the original frozen evidence archives. Their 26 entries match the preserved raw/derived files exactly. The directory layout inside each archive is unchanged. These are recorded model outputs, not additional model trials or independently authenticated provider attestations.

| Archive | Contents | Recorded calls |
|---|---|---:|
| [First-pilot evidence](pilot-001-evidence.zip) | 40 trials; seven raw files and six analysis/review files | 80 |
| [Memory-control evidence](memory-001-evidence.zip) | 300 trials; seven raw files and six analysis/review files | 420 |

[evidence-manifest.json](evidence-manifest.json) contains SHA-256 hashes for both archives and every contained file. Download the archives using GitHub's **Download raw file** control, or clone the repository normally. No API key or purchase is required to inspect or re-score the saved data.

## Verify and extract

Run from the repository root. This creates a new ignored `results/published-evidence` directory and refuses to reuse an existing one. For another reanalysis, choose a new destination. It never overwrites the original local study directories.

```bash
python3 -S - <<'PY'
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

manifest = json.loads(Path('data/evidence-manifest.json').read_text())
target = Path('results/published-evidence')
target.mkdir(parents=True, exist_ok=False)
for archive in manifest['archives']:
    path = Path(archive['path'])
    assert hashlib.sha256(path.read_bytes()).hexdigest() == archive['sha256'], path
    destination = target / archive['extraction_subdirectory']
    with ZipFile(path) as z:
        assert z.testzip() is None
        assert set(z.namelist()) == set(archive['files'])
        for name, record in archive['files'].items():
            assert not Path(name).is_absolute() and '..' not in Path(name).parts
            assert hashlib.sha256(z.read(name)).hexdigest() == record['sha256'], name
        z.extractall(destination)
print('Verified and extracted 26 original evidence files; no API calls.')
PY
```

## Audit and re-score

Run these after extraction. Output files must be new; the tools refuse to overwrite them. These commands read historical responses and send no model requests.

```bash
python3 -S -m evaluation.audit_pilot results/published-evidence/pilot/pilot-live-001 --expected-plan-sha256 4add3443a73a8e2e8944b244b3c865153f358824ffc28738fdc8026c514a00da --output results/published-evidence/pilot-audit.json
python3 -S -m evaluation.score results/published-evidence/pilot/pilot-live-001/trials.jsonl --output results/published-evidence/pilot-scoring.json
python3 -S -m evaluation.audit_memory results/published-evidence/memory/memory-live-001 --expected-plan-sha256 9500439baf60d5d1681bcf116371715a37299210fcc04c98ca0975ee7162b8d9 --output results/published-evidence/memory-audit.json
python3 -S -m evaluation.score_memory results/published-evidence/memory/memory-live-001 --output results/published-evidence/memory-scoring.json
```

Expected audit totals are 40 trials / 80 recorded calls and 300 trials / 420 recorded calls. Each re-scored JSON should equal its original run's `evaluation.json` as parsed JSON. The frozen evaluators leave unresolved human labels unknown.

## Reading the evidence

Each raw run contains `plan.json`, `manifest.json`, `schedule.json`, `calls.jsonl`, `trials.jsonl`, `summary.json` and `evaluation.json`. The first archive's analysis folder is `pilot-live-001-analysis`; the second's is `analysis`. Historical instructions inside those preserved folders may refer to the owner's original `results/` paths; use the extracted paths above for this release.

The first review packet has 11 unique summary texts; the second has 35. Omer reports completing the earlier review; item-level labels remain unreconciled in the retained packets. See [review status](../docs/review-status.md). Provisional AI labels and the anomaly trace are nonblind observations, not independent human validation. Looking at those observations before annotating affects blinding and should be disclosed. Do not merge the two studies as one condition: their tasks and policies differ.

Read the [main report](../writeup.md), [first-pilot report](../docs/reports/pilot-results.md), [memory-control report](../docs/reports/memory-pilot-results.md), and [source mapping](../docs/source-provenance.md). The results remain negative for the registered attack-goal endpoints; one summary lost useful facts. The later [defense comparison](../docs/reports/defense-results.md) preserved measured utility but did not establish a security advantage. Data release authorizes no further paid experiment.

## Defense comparison evidence

Included in this owner-approved release. The [defense archive](defense-001-evidence.zip) contains six frozen raw run files and seven separate analysis/source/test artifacts. The [defense manifest](defense-001-manifest.json) records archive and per-file hashes. The nested `analysis/executed-source.zip` contains all 44 registered source/test files, including the pre-run protocol documentation. Their original dirty-tree provenance is retained.

This run completed 240 valid trials / 480 recorded provider calls. Both formats recovered 120/120 answers and had 0/20 designated attack successes. The comparison does not establish attack reduction. Estimated usage was $0.02132775; the $10 cap was not a charge. All paid-run approvals are consumed.

From the repository root, verify and extract to a fresh directory:

```bash
python3 -S - <<'PY'
import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

m = json.loads(Path('data/defense-001-manifest.json').read_text())
archive = Path(m['path'])
assert hashlib.sha256(archive.read_bytes()).hexdigest() == m['sha256']
target = Path('results/defense-evidence-check')
target.mkdir(parents=True, exist_ok=False)
with ZipFile(archive) as z:
    assert z.testzip() is None
    assert set(z.namelist()) == set(m['files'])
    for name, item in m['files'].items():
        assert not Path(name).is_absolute() and '..' not in Path(name).parts
        assert hashlib.sha256(z.read(name)).hexdigest() == item['sha256'], name
    z.extractall(target)
plan = json.loads((target / 'defense-live-001/plan.json').read_text())
source = plan['source_provenance']
expected = {**source['source_sha256'], **source['test_sha256']}
with ZipFile(target / 'analysis/executed-source.zip') as z:
    assert z.testzip() is None
    assert set(z.namelist()) == set(expected)
    for name, digest in expected.items():
        assert hashlib.sha256(z.read(name)).hexdigest() == digest, name
print('Verified 13 evidence entries and 44 executed source/test files; no API calls.')
PY

python3 -S -m evaluation.audit_defense results/defense-evidence-check/defense-live-001 --output results/defense-evidence-check/reaudit.json
python3 -S -m evaluation.score_defense results/defense-evidence-check/defense-live-001 --output results/defense-evidence-check/rescored.json

python3 -S - <<'PY'
import json
from pathlib import Path
p = Path('results/defense-evidence-check')
assert json.loads((p/'rescored.json').read_text()) == json.loads((p/'defense-live-001/evaluation.json').read_text())
assert json.loads((p/'reaudit.json').read_text()) == json.loads((p/'analysis/audit.json').read_text())
print('Saved audit and scores reproduced without model requests.')
PY
```

The raw files are `plan.json` (including the schedule), `manifest.json`,
`calls.jsonl`, `trials.jsonl`, `summary.json` and `evaluation.json`. Derived
analysis is separate. The audit checks 960 journal entries, 480 unique request
IDs, exact contexts, decisions, usage and cost arithmetic. These are internal
consistency checks, not independent provider authentication. Free-text semantic
labels stay unknown, including 80 unassessed available-evidence policy labels.
The original two archives remain byte-identical; no replacement trial or paid
reanalysis is needed.
