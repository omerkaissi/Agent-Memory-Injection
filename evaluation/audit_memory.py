"""Offline consistency audit of a completed memory pilot; never alters raw files."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import statistics

from agent import digest
from evaluation.audit_pilot import RAW_FILES, require
from evaluation.score_memory import analyze, model_evidence


def audit(run, expected_hash):
    run = Path(run)
    raw = {name: (run / name).read_bytes() for name in RAW_FILES}
    data = {name: ([json.loads(s) for s in value.splitlines() if s.strip()]
                   if name.endswith('.jsonl') else json.loads(value)) for name, value in raw.items()}
    plan, manifest, schedule, summary, rows, journal, saved = (data[n] for n in RAW_FILES)
    require(digest({k:v for k,v in plan.items() if k != 'plan_sha256'}) == expected_hash
            == plan['plan_sha256'] == manifest['plan_sha256'] == manifest['approved_plan_sha256'],
            'Plan/approval hash mismatch')
    require(manifest['mode'] == summary['mode'] == 'live'
            and manifest['status'] == summary['status'] == 'completed', 'Not a completed live run')
    require(manifest['run_id'] == summary['run_id'], 'Run identity mismatch')
    require(schedule == plan['design']['schedule'] and len(schedule) == len(rows) == plan['planned_trials'],
            'Registered schedule mismatch')
    require([r['trial_id'] for r in rows] == [r['trial_id'] for r in schedule], 'Trial ordering mismatch')
    reevaluated = analyze(rows, plan)
    require(reevaluated == saved and reevaluated['counts'] == {'valid':len(rows)}, 'Scoring differs or is incomplete')
    calls_expected = sum(r['expected_stub_calls'] for r in schedule)
    require(calls_expected == plan['max_provider_calls'] and len(journal) == 2*calls_expected, 'Incomplete call journal')
    budget = plan['budget']; reservation = Decimal(budget['reserved_usd_per_call'])
    rates = [Decimal(budget[k]) for k in ('input_usd_per_million_tokens','output_usd_per_million_tokens')]
    tokens, fingerprints, decisions = Counter(), Counter(), Counter()
    request_ids, latencies, summaries = [], [], set()
    cost = Decimal('0'); call_number = 0
    for row in rows:
        require(row['run_id'] == manifest['run_id'] and row['status'] == 'completed'
                and row['error_type'] is None and row['mode'] == 'live', 'Incomplete or mixed trial')
        observed, summary_text = model_evidence(row)
        if summary_text is not None:
            summaries.add(summary_text)
            require([e['kind'] for e in row['events']] == ['summary','memory_replacement','reply'], 'Unexpected summary events')
            replacement = row['events'][1]
            require(replacement['before'] == row['pre_summary_memory']
                    and replacement['after'] == row['post_summary_memory'], 'Replacement snapshot mismatch')
        else:
            require([e['kind'] for e in row['events']] == ['reply'], 'Unexpected responder events')
        events = [e for e in row['events'] if e['kind'] in ('summary','reply')]
        for event in events:
            call_number += 1
            start, end = journal[2*call_number-2:2*call_number]
            require(start['kind'] == 'call_reserved' and end['kind'] == 'call_result'
                    and start['call_number'] == end['call_number'] == call_number
                    and start['trial_id'] == end['trial_id'] == row['trial_id']
                    and start['mode'] == end['mode'] == 'live', 'Journal ordering/identity mismatch')
            require(start['request'] == event['request']
                    and start['request_sha256'] == event['request_sha256'] == digest(event['request']), 'Request mismatch')
            require(end['status'] == event['status'] == 'completed' and end['error_type'] is None, 'Failed completion')
            response = end['response']
            for key in ('returned_model','usage','response_text','finish_reason','refusal','system_fingerprint'):
                require(response[key] == event[key], 'Journal/trace disagreement')
            usage = response['usage']; p, c = usage['prompt_tokens'], usage['completion_tokens']
            require(p <= budget['reserved_input_tokens_per_call'] and c <= budget['max_output_tokens_per_call'], 'Token limit exceeded')
            call_cost = (p*rates[0] + c*rates[1])/1000000
            require(Decimal(end['usage_cost_estimate_usd']) == call_cost
                    and Decimal(start['reserved_usd']) == reservation*call_number, 'Call accounting mismatch')
            require(datetime.fromisoformat(end['timestamp']) >= datetime.fromisoformat(start['timestamp']), 'Invalid timestamps')
            cost += call_cost; tokens.update(usage); fingerprints[response['system_fingerprint']] += 1
            request_ids.append(response.get('request_id')); latencies.append(end['latency_seconds'])
        decisions[(row['scenario'],row['protocol'],row['arm'],observed['decision'],str(observed['task']))] += 1
    require(all(isinstance(s,str) and s for s in request_ids) and len(set(request_ids)) == calls_expected,
            'Missing or duplicate provider request IDs')
    account = summary['accounting']
    require(account['mode'] == 'live' and account['provider_calls'] == account['dispatched_calls'] == calls_expected
            and account['stub_calls'] == account['unknown_usage_calls'] == 0
            and Decimal(account['known_usage_cost_estimate_usd']) == Decimal(account['total_cost_estimate_usd']) == cost
            and Decimal(account['reserved_cost_usd']) == reservation*calls_expected
            <= Decimal(manifest['approved_budget_usd']) <= Decimal(budget['proposed_spending_ceiling_usd']), 'Run accounting mismatch')
    require(summary['counts'] == {'completed':len(rows),'invalid':0,'error':0,'unattempted':0}
            and summary['attempted'] == summary['planned'] == len(rows), 'Pipeline counts mismatch')
    return {
        'audit_version':'completed-memory-pilot-v1','status':'passed','run_id':manifest['run_id'],
        'plan_sha256':expected_hash,'raw_sha256':{n:hashlib.sha256(b).hexdigest() for n,b in raw.items()},
        'trials':len(rows),'provider_calls':call_number,'journal_entries':len(journal),
        'unique_request_ids':len(set(request_ids)),'unique_summary_texts':len(summaries),
        'token_totals':dict(tokens),'usage_cost_estimate_usd':str(cost),'fingerprints':dict(fingerprints),
        'first_call_at':journal[0]['timestamp'],'last_call_at':journal[-1]['timestamp'],
        'call_latency_seconds':{'sum':sum(latencies),'median':statistics.median(latencies),'max':max(latencies)},
        'decisions':[{'scenario':k[0],'protocol':k[1],'arm':k[2],'decision':k[3],'task':k[4],'count':v}
                     for k,v in sorted(decisions.items())],
        'limits':'Internal consistency only, not independent provider authentication or billing verification. Completed valid runs only; no additional API call.',
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run',type=Path)
    parser.add_argument('--expected-plan-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(argv)
    try:
        result = audit(args.run,args.expected_plan_sha256)
        with args.output.open('x',encoding='utf-8') as handle:
            json.dump(result,handle,indent=2);handle.write('\n')
    except (ValueError,KeyError,TypeError,OSError) as error:
        parser.error(f'Audit failed ({type(error).__name__}); original run unchanged')
    print(f"Audit passed: {result['trials']} trials and {result['provider_calls']} calls; no new API usage.")


if __name__ == '__main__':
    main()
