import unittest
from unittest.mock import Mock,patch
import test_core
from cyai.connectors import Codex,Control,SessionBusy
class BusyTests(unittest.TestCase):
 def test_only_resume_conflict_is_recoverable(self):
  for native,error,expected in [('old','already has an active writer',SessionBusy),('old','network failed',RuntimeError),(None,'already has an active writer',RuntimeError)]:
   rpc=Mock();rpc.request.side_effect=[{},RuntimeError(error)]
   c=Codex('codex',{},None)
   with patch('cyai.connectors.JsonProcess',return_value=rpc),patch('cyai.connectors.executable',return_value=['codex']),patch.object(c,'configuration',return_value={'mcp_servers':{}}):
    with self.assertRaises(expected) as caught:c.run('test','.','',native,Control(20,lambda d:False,lambda *_:None))
    self.assertIs(type(caught.exception),expected)
   rpc.close.assert_called_once()
   self.assertNotIn('turn/start',[x.args[0] for x in rpc.request.call_args_list])
 def test_recovery_restores_context_preserves_old_binding(self):
  f=test_core.CoreTests();f.setUp()
  try:
   f.run_job();connector=f.connectors['alpha'];original=connector.run;calls=[]
   def run(prompt,root,model,native,control):
    calls.append((prompt,native))
    if native:raise SessionBusy('busy')
    return original(prompt,root,model,native,control)
   connector.run=run
   f.run_job()
   self.assertEqual(len(calls),2);self.assertIsNotNone(calls[0][1]);self.assertIsNone(calls[1][1]);self.assertIn('résultat vérifiable',calls[1][0])
   sessions=f.store.rows('SELECT native_id FROM sessions');self.assertEqual(len(sessions),2);self.assertNotEqual(sessions[0]['native_id'],sessions[1]['native_id'])
  finally:f.tearDown()

 def test_archived_resume_unarchives_same_session_once(self):
  calls=[]
  class RPC:
   resumed=False
   def request(self,method,params):
    calls.append((method,params))
    if method=='thread/resume':
     if not self.resumed:self.resumed=True;raise RuntimeError('session old is archived. Run codex unarchive')
     return {'thread':{'id':'old'}}
    if method=='turn/start':return {'turn':{'id':'turn'}}
    return {}
   def send(self,*a):pass
   def next(self):return {'method':'turn/completed','params':{'turn':{'status':'completed'}}}
   def close(self):pass
  c=Codex('codex',{},Mock(redact=lambda v:v))
  with patch('cyai.connectors.JsonProcess',return_value=RPC()),patch('cyai.connectors.executable',return_value=['codex']),patch.object(c,'configuration',return_value={'mcp_servers':{}}):
   c.run('test','.','','old',Control(20,lambda d:False,lambda *_:None))
  self.assertEqual([p for m,p in calls if m=='thread/unarchive'],[{'threadId':'old'}])
  self.assertEqual(len([m for m,p in calls if m=='thread/resume']),2)
  self.assertNotIn('thread/start',[m for m,p in calls])

 def test_failed_unarchive_is_recoverable_before_turn(self):
  from cyai.connectors import SessionUnavailable
  rpc=Mock();rpc.request.side_effect=[{},RuntimeError('session old is archived'),RuntimeError('rollout missing')]
  c=Codex('codex',{},None)
  with patch('cyai.connectors.JsonProcess',return_value=rpc),patch('cyai.connectors.executable',return_value=['codex']),patch.object(c,'configuration',return_value={'mcp_servers':{}}):
   with self.assertRaises(SessionUnavailable):c.run('test','.','','old',Control(20,lambda d:False,lambda *_:None))
  self.assertNotIn('turn/start',[x.args[0] for x in rpc.request.call_args_list])
