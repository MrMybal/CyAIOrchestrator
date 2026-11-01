import json
import unittest
import test_core
from cyai.engine import Engine
from cyai.connectors import SessionBusy

class RecoveryTests(unittest.TestCase):
    setUp=test_core.CoreTests.setUp
    tearDown=test_core.CoreTests.tearDown

    def test_shared_codex_defaults_do_not_block_other_connectors(self):
        self.store.execute('UPDATE conversations SET agent_settings=? WHERE id=?',(json.dumps({'service_tier':'priority','effort':'high'}),self.conversation))
        observed=[]
        def run(prompt,root,model,native,control):
            observed.append((control.service_tier,control.effort));return 'OK'
        self.connectors['alpha'].run=run
        id=self.engine.create({'conversation_id':self.conversation,'steps':[{'connector':'alpha','instruction':'test'}]})
        self.engine.launch(id);self.engine.jobs.join()
        self.assertEqual(observed,[('','')])
        self.assertEqual(self.store.one('SELECT status FROM missions WHERE id=?',(id,))['status'],'succeeded')

    def test_crash_report_is_durable_and_successful_steps_are_not_repeated(self):
        id=self.engine.create({'conversation_id':self.conversation,'steps':[{'connector':'alpha','instruction':'first'},{'connector':'alpha','instruction':'second'}]})
        self.engine.shutdown()
        self.store.execute("UPDATE missions SET status='running' WHERE id=?",(id,))
        self.store.execute("UPDATE steps SET status='succeeded',result='kept',attempts=1 WHERE mission_id=? AND position=0",(id,))
        self.store.execute("UPDATE steps SET status='running',attempts=1 WHERE mission_id=? AND position=1",(id,))
        self.store.event(id,None,'delta',{'text':'last saved output'})
        self.engine=Engine(self.store,self.connectors,self.policy,test_core.TestSecrets())
        self.store.recover() # repeated startup does not duplicate reports
        reports=self.store.rows("SELECT data FROM events WHERE kind='recovery_required'")
        self.assertEqual(len(reports),1)
        report=json.loads(reports[0]['data'])
        self.assertEqual(report['steps'][1]['status'],'running')
        self.assertEqual(report['last_event']['kind'],'delta')
        self.assertTrue(self.service.conversation(self.conversation)['failures'])
        self.engine.retry(id,True);self.engine.jobs.join()
        self.assertEqual(len(self.connectors['alpha'].calls),1)
        self.assertIn('REPRISE APRÈS INTERRUPTION',self.connectors['alpha'].calls[0][0])
        self.assertEqual(self.store.one('SELECT status FROM missions WHERE id=?',(id,))['status'],'succeeded')

    def test_busy_session_after_crash_does_not_spawn_duplicate(self):
        id=self.engine.create({'conversation_id':self.conversation,'steps':[{'connector':'alpha','instruction':'test'}]})
        self.engine.launch(id);self.engine.jobs.join()
        self.store.execute("UPDATE missions SET status='interrupted' WHERE id=?",(id,))
        self.store.execute("UPDATE steps SET status='interrupted' WHERE mission_id=?",(id,))
        calls=[]
        def run(prompt,root,model,native,control):
            calls.append(native);raise SessionBusy('already has an active writer')
        self.connectors['alpha'].run=run
        self.engine.retry(id,True);self.engine.jobs.join()
        self.assertEqual(len(calls),1)
        self.assertIsNotNone(calls[0])
        self.assertEqual(len(self.store.rows('SELECT * FROM sessions')),1)

    def test_parallel_retry_resumes_same_native_session(self):
        calls=[]
        def run(prompt,root,model,native,control):
            calls.append(native)
            control.emit('session',{'native_id':'persisted-session'})
            if len(calls)==1:raise ValueError('temporary failure')
            return 'OK'
        self.connectors['alpha'].run=run
        id=self.engine.create({'conversation_id':self.conversation,'concurrency':2,'steps':[{'connector':'alpha','instruction':'test'}]})
        self.engine.launch(id);self.engine.jobs.join()
        self.engine.retry(id,True);self.engine.jobs.join()
        self.assertEqual(calls,[None,'persisted-session'])
        self.assertEqual(len(self.store.rows('SELECT * FROM sessions')),1)

    def test_native_resume_sends_only_new_selected_messages(self):
        from cyai.context import build_context
        old=self.store.message(self.conversation,'user','OLD_CONTENT')
        seq=self.store.one('SELECT seq FROM messages WHERE id=?',(old,))['seq']
        new=self.store.message(self.conversation,'user','NEW_CONTENT')
        context=build_context(self.store,self.conversation,'next',{'message_ids':[old,new]},1000,seq)
        self.assertEqual(context['source_ids'],[new])
        self.assertNotIn('OLD_CONTENT',context['text'])
