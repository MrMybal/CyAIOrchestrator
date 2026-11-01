import json
import time
import unittest
from types import SimpleNamespace
import test_core
from cyai.conversation_queue import track, pump
from cyai.app_mcp import call, drain


def until(check):
    end=time.monotonic()+15
    while time.monotonic()<end:
        result=check()
        if result:return result
        time.sleep(.02)
    raise AssertionError('Condition non atteinte')


class BackgroundWorkTests(unittest.TestCase):
    def setUp(self):
        self.f=test_core.CoreTests();self.f.setUp();self.s=self.f.service;self.cid=self.f.conversation
    def tearDown(self):self.f.tearDown()
    def send(self,text,**extra):return self.s.action('continue_conversation',{'conversation_id':self.cid,'connector':'alpha','instruction':text,**extra})
    def terminal(self,mid):return self.s.store.one('SELECT status FROM missions WHERE id=?',(mid,))['status'] in ('succeeded','failed','cancelled')

    def test_user_message_waits_and_send_now_interrupts_only_current_turn(self):
        self.f.connectors['alpha'].mode='wait'
        first=self.send('Première réponse')['mission_id']
        until(lambda:self.f.connectors['alpha'].calls)
        waiting=self.send('Ma correction',request_key='queued-test')
        self.assertTrue(waiting['queued']);self.assertEqual(len(self.f.connectors['alpha'].calls),1)
        self.assertEqual(self.send('Ma correction',request_key='queued-test')['id'],waiting['id'])
        self.f.connectors['alpha'].mode='success'
        self.s.action('outbox_send_now',{'id':waiting['id']})
        until(lambda:self.s.store.one('SELECT status FROM conversation_outbox WHERE id=?',(waiting['id'],))['status']=='sent')
        mid=self.s.store.one('SELECT mission_id FROM conversation_outbox WHERE id=?',(waiting['id'],))['mission_id']
        until(lambda:self.terminal(mid))
        self.assertEqual(self.s.store.one('SELECT status FROM missions WHERE id=?',(first,))['status'],'cancelled')
        self.assertIn('Ma correction',self.f.connectors['alpha'].calls[-1][0])

    def test_delegation_returns_to_source_once(self):
        source=self.send('Évaluer les candidats')['mission_id'];until(lambda:self.terminal(source))
        child=self.s.action('create_conversation',{'project_id':self.f.project,'title':'Enfant'})['id']
        mission=self.s.action('create_mission',{'conversation_id':child,'steps':[{'connector':'beta','instruction':'Exercice'}],'launch':False})['mission_id']
        track(self.s,self.cid,{'mission_id':mission})
        self.s.action('launch_mission',{'mission_id':mission})
        until(lambda:self.terminal(mission))
        until(lambda:len(self.f.connectors['alpha'].calls)==2)
        until(lambda:not self.s.store.rows("SELECT id FROM missions WHERE conversation_id=? AND status IN ('queued','running')",(self.cid,)))
        pump(self.s);pump(self.s)
        self.assertEqual(len(self.f.connectors['alpha'].calls),2)
        self.assertIn(mission,self.f.connectors['alpha'].calls[-1][0])

    def test_batch_hidden_parallel_and_prompt_isolation_including_multiturn(self):
        self.s.store.message(self.cid,'assistant','SECRET PRECEDENT')
        batch=self.s.action('evaluation_prepare',{'conversation_id':self.cid,'candidates':[{'connector':'alpha','model':'one'},{'connector':'beta','model':'two'}],'concurrency':4})
        mission=self.s.store.one('SELECT * FROM missions WHERE id=?',(batch['mission_id'],))
        self.assertEqual(batch['cases'],24)
        self.assertNotIn(mission['conversation_id'],[c['id'] for c in self.s.state()['conversations']])
        self.assertNotIn(mission['conversation_id'],[c['id'] for c in self.s.project(self.f.project)['conversations']])
        self.assertEqual(self.s.conversation(self.cid)['background'][0]['id'],mission['id'])
        self.s.action('launch_mission',{'mission_id':mission['id']})
        until(lambda:self.terminal(mission['id']))
        self.assertEqual(self.s.store.one('SELECT status FROM missions WHERE id=?',(mission['id'],))['status'],'succeeded')
        for connector in self.f.connectors.values():
            self.assertEqual(len(connector.calls),13)
            self.assertEqual(sum(native is not None for _,native in connector.calls),1)
            for prompt,native in connector.calls:
                self.assertNotIn('SECRET PRECEDENT',prompt)
                self.assertNotIn('cyai-continuity',prompt)
                self.assertNotIn('Mémoire active du projet',prompt)
        result=self.s.action('evaluation_results',{'mission_id':mission['id']})
        self.assertEqual(len(result['cases']),24)
        self.assertTrue(any(r['grade']['status']=='fail' for r in result['cases']))

    def test_deferred_work_does_not_wait_for_unrelated_conversation(self):
        self.f.connectors['alpha'].mode='wait'
        unrelated=self.send('Longue opération')['mission_id']
        until(lambda:self.f.connectors['alpha'].calls)
        source=self.s.action('create_conversation',{'project_id':self.f.project})['id']
        child=self.s.action('create_conversation',{'project_id':self.f.project})['id']
        mission=self.s.action('create_mission',{'conversation_id':child,'steps':[{'connector':'beta','instruction':'Indépendant'}],'launch':False})['mission_id']
        self.s.store.execute("INSERT INTO mcp_jobs(id,action,args,projects,status,created_at,conversation_id) VALUES(?,?,?,?,?,?,?)",('deferred','launch_mission',json.dumps({'mission_id':mission}),json.dumps([self.f.project]),'pending','now',source))
        drain(self.s)
        until(lambda:self.terminal(mission))
        self.assertEqual(self.s.store.one('SELECT status FROM missions WHERE id=?',(unrelated,))['status'],'running')

    def test_pending_outbox_survives_service_reinitialization_and_no_silent_retry(self):
        from cyai.conversation_queue import enqueue, init
        with self.s.engine.lock:
            waiting=enqueue(self.s,{'conversation_id':self.cid,'connector':'alpha','instruction':'Après redémarrage','request_key':'restart'})
            self.s.store.execute("UPDATE conversation_outbox SET status='sending' WHERE id=?",(waiting['id'],))
            init(self.s)
            pump(self.s)
            self.assertEqual(self.s.store.one('SELECT status FROM conversation_outbox WHERE id=?',(waiting['id'],))['status'],'interrupted')
            self.assertEqual(len(self.f.connectors['alpha'].calls),0)
            self.s.action('outbox_retry',{'id':waiting['id']})
        until(lambda:len(self.f.connectors['alpha'].calls)==1)

    def test_batch_idempotency_and_parent_permissions(self):
        self.s.action('approval_settings',{'conversation_id':self.cid,'mode':'auto'})
        data={'conversation_id':self.cid,'candidates':[{'connector':'alpha'}],'request_key':'same-batch'}
        a=self.s.action('evaluation_prepare',data);b=self.s.action('evaluation_prepare',data)
        self.assertEqual(a['mission_id'],b['mission_id'])
        self.f.connectors['alpha'].mode='approval'
        self.s.action('launch_mission',{'mission_id':a['mission_id']})
        until(lambda:self.terminal(a['mission_id']))
        self.assertEqual(self.s.store.one('SELECT status FROM missions WHERE id=?',(a['mission_id'],))['status'],'succeeded')
        self.assertEqual(self.s.engine.approvals,{})

    def test_raw_turn_usage_is_accumulated_without_duplicate_stream_counts(self):
        from unittest.mock import patch
        original=self.f.connectors['alpha'].run
        def answer(prompt,root,model,native,control):
            control.emit('usage',{'input_tokens':5,'output_tokens':1})
            control.emit('usage',{'input_tokens':5,'output_tokens':2})
            return original(prompt,root,model,native,control)
        with patch.object(self.f.connectors['alpha'],'run',side_effect=answer):
            batch=self.s.action('evaluation_prepare',{'conversation_id':self.cid,'candidates':[{'connector':'alpha'}]})
            self.s.action('launch_mission',{'mission_id':batch['mission_id']})
            until(lambda:self.terminal(batch['mission_id']))
        case=next(x for x in self.s.action('evaluation_results',{'mission_id':batch['mission_id']})['cases'] if x['case']=='revision-A')
        self.assertEqual(case['usage']['input_tokens'],10)
        self.assertEqual(case['usage']['output_tokens'],4)
