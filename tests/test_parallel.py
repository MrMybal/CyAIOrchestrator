import threading
import unittest
import test_core
from cyai.store import uid

class ParallelTests(unittest.TestCase):
    setUp=test_core.CoreTests.setUp
    tearDown=test_core.CoreTests.tearDown

    def test_branches_overlap_and_join_waits_with_isolated_sessions(self):
        barrier=threading.Barrier(3,timeout=3)
        finished=set();lock=threading.Lock();prompts={}
        def run(prompt,root,model,native,control):
            # Match the current instruction at the end of the context, not the mission message.
            name=prompt.split('TASK_ID:')[-1].split()[0]
            prompts[name]=(prompt,native)
            control.emit('session',{'native_id':uid()})
            if name.startswith('BRANCH_'):barrier.wait()
            if name=='JOIN_TASK':self.assertTrue({'BRANCH_A','BRANCH_B','BRANCH_C'}<=finished)
            with lock:finished.add(name)
            return 'OUTPUT_'+name
        self.connectors['alpha'].run=run
        names=['ROOT_TASK','BRANCH_A','BRANCH_B','BRANCH_C','JOIN_TASK']
        deps=[[],[0],[0],[0],[1,2,3]]
        spec={'conversation_id':self.conversation,'concurrency':3,'steps':[{'name':n,'instruction':'TASK_ID:'+n,'connector':'alpha','model':'same','depends_on':d} for n,d in zip(names,deps)]}
        id=self.engine.create(spec);self.engine.launch(id);self.engine.jobs.join()
        self.assertEqual(self.store.one('SELECT status FROM missions WHERE id=?',(id,))['status'],'succeeded')
        self.assertEqual(len(prompts),5)
        self.assertTrue(all(native is None for _,native in prompts.values()))
        for name in ['BRANCH_A','BRANCH_B','BRANCH_C']:
            self.assertIn('OUTPUT_ROOT_TASK',prompts[name][0])
            self.assertNotIn('OUTPUT_BRANCH_',prompts[name][0])
        for name in ['BRANCH_A','BRANCH_B','BRANCH_C']:self.assertIn('OUTPUT_'+name,prompts['JOIN_TASK'][0])

    def test_failure_blocks_only_dependents(self):
        def run(prompt,root,model,native,control):
            if prompt.split('TASK_ID:')[-1].split()[0]=='FAIL':raise ValueError('failure')
            return 'success'
        self.connectors['alpha'].run=run
        steps=[{'connector':'alpha','instruction':'TASK_ID:'+x,'depends_on':deps} for x,deps in [('FAIL',[]),('INDEPENDENT',[]),('BLOCKED',[0])]]
        id=self.engine.create({'conversation_id':self.conversation,'concurrency':2,'steps':steps})
        self.engine.launch(id);self.engine.jobs.join()
        rows=self.store.rows('SELECT status FROM steps WHERE mission_id=? ORDER BY position',(id,))
        self.assertEqual([r['status'] for r in rows],['failed','succeeded','skipped'])

    def test_parallel_approvals_and_cancel_are_independent(self):
        import time
        self.connectors['alpha'].mode='approval'
        steps=[{'connector':'alpha','instruction':str(i),'depends_on':[]} for i in range(2)]
        id=self.engine.create({'conversation_id':self.conversation,'concurrency':2,'steps':steps})
        self.engine.launch(id)
        end=time.monotonic()+3
        while len(self.engine.approvals)<2 and time.monotonic()<end:time.sleep(.01)
        self.assertEqual(len(self.engine.approvals),2)
        key=next(iter(self.engine.approvals));self.engine.approve(key,True)
        while time.monotonic()<end:
            if self.store.rows("SELECT id FROM steps WHERE mission_id=? AND status='succeeded'",(id,)):break
            time.sleep(.01)
        self.assertEqual(self.store.one('SELECT status FROM missions WHERE id=?',(id,))['status'],'awaiting_approval')
        self.engine.cancel(id);self.engine.jobs.join()
        self.assertFalse(self.engine.approvals)
        self.assertEqual(self.store.one('SELECT status FROM missions WHERE id=?',(id,))['status'],'cancelled')
        self.assertEqual(len(self.store.rows("SELECT id FROM steps WHERE mission_id=? AND status='succeeded'",(id,))),1)

    def test_graceful_pause_survives_engine_restart(self):
        from cyai.engine import Engine
        started=threading.Event();release=threading.Event();calls=[]
        def run(prompt,root,model,native,control):
            name=prompt.split('TASK_ID:')[-1].split()[0];calls.append(name)
            if name=='FIRST':
                started.set()
                if not release.wait(3):raise ValueError('test timeout')
            return 'OK_'+name
        self.connectors['alpha'].run=run
        steps=[{'connector':'alpha','instruction':'TASK_ID:'+name,'depends_on':deps} for name,deps in [('FIRST',[]),('NEXT',[0])]]
        id=self.engine.create({'conversation_id':self.conversation,'concurrency':32,'steps':steps})
        self.engine.launch(id);self.assertTrue(started.wait(2))
        self.engine.pause(id)
        self.assertEqual(self.store.one('SELECT status FROM missions WHERE id=?',(id,))['status'],'pausing')
        release.set();self.engine.jobs.join()
        self.assertEqual(calls,['FIRST'])
        self.assertEqual(self.store.one('SELECT status FROM missions WHERE id=?',(id,))['status'],'paused')
        self.engine.shutdown()
        self.engine=Engine(self.store,self.connectors,self.policy,test_core.TestSecrets())
        self.assertEqual(self.store.one('SELECT status FROM missions WHERE id=?',(id,))['status'],'paused')
        self.engine.resume(id);self.engine.jobs.join()
        self.assertEqual(calls,['FIRST','NEXT'])
        self.assertEqual(self.store.one('SELECT status FROM missions WHERE id=?',(id,))['status'],'succeeded')
        self.assertEqual([r['attempts'] for r in self.store.rows('SELECT attempts FROM steps WHERE mission_id=? ORDER BY position',(id,))],[1,1])

    def test_concurrency_32_allowed_and_33_rejected(self):
        spec={'conversation_id':self.conversation,'steps':[{'connector':'alpha','instruction':'OK'}],'concurrency':32}
        self.engine.create(spec)
        with self.assertRaises(ValueError):self.engine.create({**spec,'concurrency':33})

    def test_other_conversation_starts_while_first_waits_for_approval(self):
        import time
        self.connectors['alpha'].mode='approval'
        first=self.engine.create({'conversation_id':self.conversation,'steps':[{'connector':'alpha','instruction':'first'}]})
        self.engine.launch(first)
        deadline=time.monotonic()+3
        while not self.engine.approvals and time.monotonic()<deadline:time.sleep(.01)
        self.assertTrue(self.engine.approvals)
        other=self.service.action('create_conversation',{'project_id':self.project,'title':'Independent chat'})['id']
        second=self.engine.create({'conversation_id':other,'steps':[{'connector':'beta','instruction':'second'}]})
        self.engine.launch(second)
        try:
            deadline=time.monotonic()+3
            while time.monotonic()<deadline:
                if self.store.one('SELECT status FROM missions WHERE id=?',(second,))['status']=='succeeded':break
                time.sleep(.01)
            self.assertEqual(self.store.one('SELECT status FROM missions WHERE id=?',(second,))['status'],'succeeded')
            self.assertEqual(self.store.one('SELECT status FROM missions WHERE id=?',(first,))['status'],'awaiting_approval')
        finally:
            self.engine.cancel(first);self.engine.jobs.join()
