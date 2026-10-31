"""Pilot and budget contracts. All 'live' fixtures use in-memory fake transports."""
from __future__ import annotations

import contextlib
import copy
from datetime import date
from decimal import Decimal
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from agent import digest, SimpleAgent
from evaluation.score import analyze
from experiments.offline import OfflineClient
from experiments.pilot_transport import GuardedClient, PilotStopped, ReservationBudget, build_sdk_client
from experiments.plan_pilot import pilot_plan
from experiments.run_pilot import main, make_schedule, run_pilot, validate_approval

try:
    import httpx
    from openai import OpenAI
except ImportError:
    OpenAI = None


def response(*, model="gpt-4o-mini-2024-07-18", usage=True, text='{"decision":"defer","task":null}', finish="stop"):
    return SimpleNamespace(model=model, choices=[SimpleNamespace(finish_reason=finish,
                           message=SimpleNamespace(content=text, refusal=None))],
                           usage=SimpleNamespace(prompt_tokens=100, completion_tokens=20, total_tokens=120) if usage else None)


class FakeProvider:
    def __init__(self, action=None):
        self.calls = 0
        self.action = action or (lambda request: response())
        self.chat = SimpleNamespace(completions=self)
    def create(self, **request):
        self.calls += 1
        return self.action(request)


class PilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.plan = pilot_plan()
        for name in ("connect", "connect_ex"):
            guard = patch.object(socket.socket, name, side_effect=AssertionError("Network forbidden"))
            guard.start(); self.addCleanup(guard.stop)
        guard = patch('socket.create_connection', side_effect=AssertionError('Network forbidden'))
        guard.start(); self.addCleanup(guard.stop)

    def guarded(self, provider=None, **kwargs):
        handle = (self.path / (str(len(list(self.path.iterdir()))) + '.jsonl')).open('w')
        self.addCleanup(handle.close)
        client = GuardedClient(provider or FakeProvider(), self.plan, mode='live', ceiling='2.00', ledger=handle, **kwargs)
        client.trial_id='SYNTHETIC_TEST_ONLY'
        return client, handle

    def request(self):
        return {'model':self.plan['model'], **self.plan['settings'], 'messages':[{'role':'user','content':'Synthetic'}]}

    def test_exact_call_and_cost_caps(self):
        budget = ReservationBudget(self.plan,'2')
        for _ in range(80): budget.reserve()
        self.assertEqual(budget.reserved, Decimal('1.548288'))
        with self.assertRaises(PilotStopped): budget.reserve()
        budget = ReservationBudget(self.plan,'0.0193536')
        budget.reserve()
        with self.assertRaises(PilotStopped): budget.reserve()
        for ceiling in ('NaN','Infinity','0','-1'):
            with self.assertRaises(ValueError): ReservationBudget(self.plan,ceiling)

    def test_reject_model_settings_and_oversized_input_before_dispatch(self):
        for key,value in (('model','another-model'),('n',2),('stream',True),('tools',[])):
            client,_=self.guarded();request=self.request();request[key]=value
            with self.assertRaises(PilotStopped): client.create(**request)
            self.assertEqual(client.dispatched,0)
        client,_=self.guarded();request=self.request();request['messages'][0]['content']='x'*32001
        with self.assertRaises(PilotStopped):client.create(**request)
        self.assertEqual(client.dispatched,0)

    def test_journal_precedes_call_and_failure_reservation_is_not_refunded(self):
        client,handle=self.guarded()
        def fail(request):
            self.assertEqual(json.loads(Path(handle.name).read_text())['kind'],'call_reserved')
            raise RuntimeError('DO_NOT_LEAK_SECRET_SENTINEL')
        client.provider=FakeProvider(fail)
        with self.assertRaises(PilotStopped):client.create(**self.request())
        self.assertEqual(client.budget.reserved,Decimal('0.0193536'))
        self.assertEqual(client.accounting()['unknown_usage_calls'],1)
        self.assertIsNone(client.accounting()['total_cost_estimate_usd'])
        self.assertNotIn('DO_NOT_LEAK_SECRET_SENTINEL',Path(handle.name).read_text())
        with self.assertRaises(PilotStopped):client.create(**self.request())
        self.assertEqual(client.provider.calls,1)

    def test_disk_failure_prevents_dispatch(self):
        client,_=self.guarded()
        with patch('experiments.pilot_transport.append_record',side_effect=OSError('Disk full')):
            with self.assertRaises(OSError):client.create(**self.request())
        self.assertEqual(client.dispatched,0)
        self.assertTrue(client.halted)

    def test_usage_model_and_token_inconsistencies_stop_run(self):
        bad=[response(usage=False),response(model='unexpected'),response(text={'bad':'shape'})]
        for attr,value in (('prompt_tokens',128001),('completion_tokens',257),('total_tokens',999),('prompt_tokens',True)):
            r=response();setattr(r.usage,attr,value);bad.append(r)
        for r in bad:
            client,_=self.guarded(FakeProvider(lambda request:r))
            with self.assertRaises(PilotStopped):client.create(**self.request())
            self.assertTrue(client.halted)

    def test_plan_approval_rejects_changes_and_expired_price(self):
        validate_approval(self.plan,self.plan['plan_sha256'],'2.00',today=date(2026,10,30))
        for amount in ('1','2.01','NaN','Infinity'):
            with self.assertRaises(ValueError):validate_approval(self.plan,self.plan['plan_sha256'],amount)
        changed=copy.deepcopy(self.plan);changed['settings']['temperature']=1
        with self.assertRaises(ValueError):validate_approval(changed,self.plan['plan_sha256'],'2')
        with self.assertRaises(ValueError):validate_approval(self.plan,self.plan['plan_sha256'],'2',today=date(2026,11,15))
        with self.assertRaises(ValueError):validate_approval(self.plan,'wrong','2')

    def test_cli_missing_approval_never_loads_sdk_or_creates_output(self):
        target=self.path/'no-output'
        with patch('experiments.run_pilot.build_sdk_client',side_effect=AssertionError('Not allowed')):
            with contextlib.redirect_stderr(io.StringIO()),self.assertRaises(SystemExit) as e:
                main(['--output',str(target),'--execute'])
        self.assertEqual(e.exception.code,2);self.assertFalse(target.exists())

    def test_full_rehearsal_and_no_overwrite(self):
        target=self.path/'rehearsal'
        with patch('experiments.run_pilot.build_sdk_client',side_effect=AssertionError('SDK forbidden')):
            summary=run_pilot(target)
        self.assertEqual(summary['counts']['completed'],40)
        self.assertEqual(summary['accounting']['stub_calls'],80)
        self.assertEqual(summary['accounting']['provider_calls'],0)
        self.assertEqual(summary['accounting']['total_cost_estimate_usd'],'0')
        scores=json.loads((target/'evaluation.json').read_text())
        self.assertTrue(all(g['attack_success']['rate'] is None for g in scores['groups'].values()))
        with self.assertRaises(FileExistsError):run_pilot(target)

    def test_abort_keeps_failed_attempt_and_unattempted_schedule(self):
        provider=FakeProvider(lambda request: (_ for _ in ()).throw(RuntimeError('Private SDK text')))
        target=self.path/'aborted'
        summary=run_pilot(target,mode='live',plan=self.plan,approved_hash=self.plan['plan_sha256'],provider=provider)
        self.assertEqual(summary['status'],'aborted')
        self.assertEqual(summary['attempted'],1)
        self.assertEqual(summary['counts']['unattempted'],39)
        records=[json.loads(x) for x in (target/'trials.jsonl').read_text().splitlines()]
        report=analyze(records)
        self.assertEqual(sum(g['attempted'] for g in report['groups'].values()),1)
        self.assertEqual(len(records),40)
        self.assertNotIn('Private SDK text',(target/'calls.jsonl').read_text())

    def test_interruption_and_truncated_summary_are_not_retried(self):
        provider=FakeProvider(lambda request: (_ for _ in ()).throw(KeyboardInterrupt()))
        summary=run_pilot(self.path/'interrupt',mode='live',plan=self.plan,approved_hash=self.plan['plan_sha256'],provider=provider)
        self.assertEqual(summary['status'],'aborted');self.assertEqual(provider.calls,1)
        provider=FakeProvider(lambda request:response(finish='length'))
        summary=run_pilot(self.path/'truncated',mode='live',plan=self.plan,approved_hash=self.plan['plan_sha256'],provider=provider)
        self.assertEqual(summary['counts']['invalid'],40)
        self.assertEqual(provider.calls,40) # No downstream call after an invalid summary.

    def test_schedule_balance_and_import_safety(self):
        schedule=make_schedule(self.plan,'test')
        self.assertEqual(len({s['trial_id'] for s in schedule}),40)
        self.assertEqual(schedule,make_schedule(self.plan,'test'))
        script="import sys;sys.modules['openai']=None;import experiments.run_pilot,experiments.pilot_transport"
        r=subprocess.run([sys.executable,'-S','-c',script],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr);self.assertEqual(r.stdout,'')

    def test_generation_settings_do_not_override_model_or_messages(self):
        for name in ('model','messages','tools'):
            with self.assertRaises(ValueError):SimpleAgent(generation_settings={name:'invalid'})

    @unittest.skipUnless(OpenAI is not None,'Optional clean SDK environment required')
    def test_real_sdk_mock_http_serialization_and_no_automatic_retries(self):
        captured=[]
        def handle(request):
            captured.append(request)
            return httpx.Response(429,json={'error':{'message':'PRIVATE_ERROR_SENTINEL','type':'rate_limit'}})
        sdk=OpenAI(api_key='unit-test-not-a-secret',max_retries=0,
                   http_client=httpx.Client(transport=httpx.MockTransport(handle)))
        self.addCleanup(sdk.close)
        client,ledger=self.guarded(sdk)
        with self.assertRaises(PilotStopped):client.create(**self.request())
        self.assertEqual(len(captured),1)
        self.assertEqual(str(captured[0].url),'https://api.openai.com/v1/chat/completions')
        sent=json.loads(captured[0].content)
        self.assertEqual(sent['max_completion_tokens'],256)
        self.assertFalse(sent['store'])
        self.assertNotIn('PRIVATE_ERROR_SENTINEL',Path(ledger.name).read_text())

    @unittest.skipUnless(OpenAI is not None,'Optional clean SDK environment required')
    def test_real_sdk_full_pilot_with_fake_http_responses(self):
        requests=[]
        def handle(request):
            body=json.loads(request.content);requests.append(body)
            if len(body['messages'])==1:text='Synthetic summary; no empirical model output.'
            elif 'priority of Task A is 9' in body['messages'][-1]['content']:text='{"decision":"choose","task":"A"}'
            else:text='{"decision":"defer","task":null}'
            return httpx.Response(200,json={'id':'fixture','object':'chat.completion','created':0,
                'model':self.plan['model'],'choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':text}}],
                'usage':{'prompt_tokens':100,'completion_tokens':20,'total_tokens':120}})
        sdk=OpenAI(api_key='unit-test-not-a-secret',max_retries=0,http_client=httpx.Client(transport=httpx.MockTransport(handle)))
        self.addCleanup(sdk.close)
        target=self.path/'sdk-fixture'
        summary=run_pilot(target,mode='live',plan=self.plan,approved_hash=self.plan['plan_sha256'],provider=sdk)
        self.assertEqual(summary['status'],'completed');self.assertEqual(len(requests),80)
        self.assertEqual(Decimal(summary['accounting']['known_usage_cost_estimate_usd']),Decimal('0.00216'))
        scores=json.loads((target/'evaluation.json').read_text())
        self.assertTrue(all(g['counts'].get('valid')==10 for g in scores['groups'].values()))

    def test_sdk_factory_rejects_environment_endpoint_and_debug_overrides(self):
        for env in ({'OPENAI_BASE_URL':'https://unapproved.example'},{'OPENAI_LOG':'debug'},{}):
            with patch.dict(os.environ,env,clear=True),self.assertRaises(PilotStopped):
                build_sdk_client(self.plan)

    @unittest.skipUnless(OpenAI is not None,'Optional clean SDK environment required')
    def test_private_key_prompt_requires_terminal_and_never_sets_environment(self):
        with patch.dict(os.environ,{},clear=True),patch('sys.stdin.isatty',return_value=False),patch('getpass.getpass') as prompt:
            with self.assertRaises(PilotStopped):build_sdk_client(self.plan,prompt_key=True)
            prompt.assert_not_called()
        with patch.dict(os.environ,{},clear=True),patch('sys.stdin.isatty',return_value=True),patch('getpass.getpass',return_value='unit-test-not-a-secret'):
            sdk=build_sdk_client(self.plan,prompt_key=True)
            self.addCleanup(sdk.close)
            self.assertNotIn('OPENAI_API_KEY',os.environ)

    @unittest.skipUnless(OpenAI is not None,'Optional clean SDK environment required')
    def test_production_factory_configuration_without_network(self):
        with patch.dict(os.environ,{'OPENAI_API_KEY':'unit-test-not-a-secret'},clear=True):
            sdk=build_sdk_client(self.plan)
        self.addCleanup(sdk.close)
        self.assertEqual(sdk.max_retries,0)
        self.assertEqual(str(sdk.base_url),'https://api.openai.com/v1/')
        self.assertEqual(sdk.timeout,30)
        with patch.dict(os.environ,{'OPENAI_API_KEY':'unit-test-not-a-secret'},clear=True),patch('experiments.pilot_transport.metadata.version',return_value='wrong'):
            with self.assertRaises(PilotStopped):build_sdk_client(self.plan)


if __name__=='__main__':unittest.main()
