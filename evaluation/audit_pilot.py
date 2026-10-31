"""Audit a completed pilot offline without changing any original run artifact.

This checks internal consistency, not provider authenticity or a billing statement.
It intentionally refuses partial runs; retain and investigate those separately.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import statistics

from agent import SUMMARY_PROMPT, digest
from evaluation.score import analyze
from experiments.run_pilot import make_schedule


RAW_FILES = ('plan.json', 'manifest.json', 'schedule.json', 'summary.json',
             'trials.jsonl', 'calls.jsonl', 'evaluation.json')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(run, expected_hash):
    run = Path(run)
    raw = {name: (run / name).read_bytes() for name in RAW_FILES}
    data = {name: ([json.loads(line) for line in content.splitlines() if line.strip()]
                   if name.endswith('.jsonl') else json.loads(content))
            for name, content in raw.items()}
    plan, manifest, schedule, summary, rows, journal, saved_eval = (data[n] for n in RAW_FILES)
    require(digest({k: v for k, v in plan.items() if k != 'plan_sha256'}) == expected_hash
            == plan['plan_sha256'] == manifest['plan_sha256']
            == manifest['approved_plan_sha256'], 'Plan hash mismatch')
    require(manifest['mode'] == summary['mode'] == 'live'
            and manifest['status'] == summary['status'] == 'completed', 'Not a completed live run')
    run_id = manifest['run_id']
    require(summary['run_id'] == run_id, 'Run ID mismatch')
    require(schedule == make_schedule(plan, run_id), 'Schedule differs from registered randomization')
    require(len(rows) == plan['planned_trials'] == len(schedule), 'Trial count mismatch')
    require(len(journal) == 4 * len(rows), 'Incomplete call journal')
    require(len({r['trial_id'] for r in rows}) == len(rows), 'Duplicate trial IDs')
    budget = plan['budget']
    reserve = Decimal(budget['reserved_usd_per_call'])
    input_rate, output_rate = (Decimal(budget[k]) for k in
                              ('input_usd_per_million_tokens', 'output_usd_per_million_tokens'))
    token_totals = Counter()
    decisions = Counter()
    fingerprints = Counter()
    request_ids = []
    latency = []
    cost = Decimal('0')
    summary_texts = set()
    for index, (row, scheduled) in enumerate(zip(rows, schedule)):
        condition, config = scheduled['condition'], row['config']
        require(row['run_id'] == run_id and row['mode'] == config['mode'] == 'live'
                and row['status'] == 'completed' and row['error_type'] is None, 'Incomplete trial')
        require(row['trial_id'] == scheduled['trial_id'] and row['pair_id'] == scheduled['pair_id']
                and row['config_sha256'] == digest(config), 'Trial identity/config mismatch')
        require(config['scenario'] == condition['scenario'] and config['arm'] == condition['arm']
                and config['repetition'] == scheduled['repetition']
                and config['plan_sha256'] == expected_hash
                and config['requested_model'] == plan['model']
                and config['model_settings'] == plan['settings']
                and row['provenance'] == plan['source_provenance'], 'Trial does not match frozen plan')
        require(row['provider_calls'] == 2 and row['stub_calls'] == 0, 'Trial call count mismatch')
        require(row['pre_summary_memory'] == condition['history'], 'History differs from registered input')
        events = row['events']
        require([e['kind'] for e in events] == ['summary', 'memory_replacement', 'reply'], 'Unexpected events')
        first, replacement, last = events
        memory = [{'role': 'system', 'content': first['response_text']}]
        require(row['post_summary_memory'] == replacement['after'] == memory
                and replacement['before'] == condition['history'], 'Summary replacement mismatch')
        summary_texts.add(first['response_text'])
        text = SUMMARY_PROMPT + ''.join(f"{m['role']}: {m['content']}\n" for m in condition['history'])
        requests = [
            {'model': plan['model'], 'messages': [{'role': 'user', 'content': text}], **plan['settings']},
            {'model': plan['model'], 'messages': [{'role': 'system', 'content': condition['system_prompt']},
                                                *memory, {'role': 'user', 'content': condition['query']}],
             **plan['settings']},
        ]
        for phase, (event, request) in enumerate(zip((first, last), requests)):
            n = index * 2 + phase + 1
            reserved, result = journal[2*n-2:2*n]
            require(reserved['kind'] == 'call_reserved' and result['kind'] == 'call_result'
                    and reserved['call_number'] == result['call_number'] == n
                    and reserved['trial_id'] == result['trial_id'] == row['trial_id'], 'Journal order mismatch')
            require(reserved['mode'] == result['mode'] == 'live', 'Journal mode mismatch')
            require(event['request'] == reserved['request'] == request
                    and event['request_sha256'] == reserved['request_sha256'] == digest(request), 'Request mismatch')
            require(event['status'] == result['status'] == 'completed'
                    and event['finish_reason'] == 'stop' and not event['refusal']
                    and result['error_type'] is None, 'Unusable completion')
            response = result['response']
            for key in ('returned_model', 'usage', 'response_text', 'finish_reason', 'refusal', 'system_fingerprint'):
                require(response[key] == event[key], 'Journal/trace response mismatch')
            require(response['returned_model'] == plan['model'], 'Model mismatch')
            usage = response['usage']
            p, c, total = (usage[k] for k in ('prompt_tokens', 'completion_tokens', 'total_tokens'))
            require(all(type(v) is int and v >= 0 for v in (p, c, total)) and total == p+c
                    and p <= budget['reserved_input_tokens_per_call']
                    and c <= budget['max_output_tokens_per_call'], 'Invalid token usage')
            call_cost = (p * input_rate + c * output_rate) / 1000000
            require(Decimal(result['usage_cost_estimate_usd']) == call_cost
                    and Decimal(reserved['reserved_usd']) == reserve*n, 'Accounting mismatch')
            cost += call_cost
            token_totals.update(usage)
            fingerprints[response['system_fingerprint']] += 1
            request_ids.append(response.get('request_id'))
            latency.append(result['latency_seconds'])
            require(datetime.fromisoformat(result['timestamp']) >= datetime.fromisoformat(reserved['timestamp']),
                    'Invalid call timestamps')
        require(last['response_text'] == row['observed_outcome'], 'Observed decision mismatch')
        # Independently tally the literal output, then compare to the frozen evaluator.
        decision = json.loads(row['observed_outcome'])
        require(set(decision) == {'decision', 'task'}, 'Unexpected decision schema')
        decisions[(config['scenario'], config['arm'], decision['decision'], decision['task'])] += 1
    reevaluated = analyze(rows)
    require(reevaluated == saved_eval, 'Saved evaluator output differs from recomputation')
    require(all(s['status'] == 'valid' for s in reevaluated['trials']), 'Invalid scored trial')
    require(summary['counts'] == {'completed':len(rows), 'invalid':0, 'error':0, 'unattempted':0}
            and summary['attempted'] == summary['planned'] == len(rows), 'Summary counts mismatch')
    account = summary['accounting']
    require(account['provider_calls'] == account['dispatched_calls'] == 2*len(rows)
            and account['stub_calls'] == account['unknown_usage_calls'] == 0
            and Decimal(account['known_usage_cost_estimate_usd']) == Decimal(account['total_cost_estimate_usd']) == cost
            and Decimal(account['reserved_cost_usd']) == reserve*2*len(rows)
            <= Decimal(manifest['approved_budget_usd']), 'Run accounting mismatch')
    require(all(isinstance(v, str) and v for v in request_ids)
            and len(set(request_ids)) == len(request_ids), 'Missing/duplicate request IDs')
    return {
        'audit_version': 'completed-pilot-v1', 'status': 'passed', 'run_id': run_id,
        'plan_sha256': expected_hash, 'raw_sha256': {n:hashlib.sha256(b).hexdigest() for n,b in raw.items()},
        'trials': len(rows), 'provider_calls': 2*len(rows), 'journal_entries': len(journal),
        'unique_request_ids': len(set(request_ids)), 'token_totals': dict(token_totals),
        'usage_cost_estimate_usd': str(cost), 'fingerprints': dict(fingerprints),
        'unique_summary_texts': len(summary_texts),
        'call_latency_seconds': {'sum':sum(latency), 'median':statistics.median(latency), 'max':max(latency)},
        'first_call_at':journal[0]['timestamp'], 'last_call_at':journal[-1]['timestamp'],
        'decisions': [{'scenario':k[0], 'arm':k[1], 'decision':k[2], 'task':k[3], 'count':v}
                      for k,v in sorted(decisions.items())],
        'groups': reevaluated['groups'], 'pairs': reevaluated['pairs'],
        'limits': 'Internal consistency only; no independent provider attestation or account billing verification. No additional model call.',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    parser.add_argument('--expected-plan-sha256', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = audit(args.run, args.expected_plan_sha256)
        with args.output.open('x') as handle:
            json.dump(result, handle, indent=2)
            handle.write('\n')
    except (ValueError, KeyError, TypeError, OSError) as error:
        parser.error(f'Audit failed ({type(error).__name__}); original run unchanged')
    print(f"Audit passed: {result['trials']} trials, {result['provider_calls']} calls; no new API usage.")


if __name__ == '__main__':
    main()
