import io,json,unittest
from unittest.mock import patch
from cyai.connectors import Control,Cancelled,Anthropic,ClaudeCode
from cyai.local_tools import run
import test_core

class LimitTests(unittest.TestCase):
 def test_local_can_run_more_than_twelve_tools_and_still_cancel(self):
  calls=[];control=Control(0,lambda _:True,lambda *_:None);control.plugin_call=lambda *a:{}
  def response(req,**kwargs):
   calls.append(json.loads(req.data))
   body={'message':{'tool_calls':[{'function':{'name':'cyai_actions','arguments':{}}}]},'done':True} if len(calls)<=15 else {'message':{'content':'done'},'done':True}
   return io.BytesIO((json.dumps(body)+'\n').encode())
  with patch('urllib.request.urlopen',side_effect=response):self.assertEqual(run('http://localhost',{},'test',control,ollama=True),'done')
  self.assertEqual(len(calls),16)
  control.cancelled.set()
  with self.assertRaises(Cancelled):run('http://localhost',{},'test',control)

 def test_anthropic_partial_text_continues_instead_of_failing(self):
  def stream(text,reason):
   events=[{'type':'content_block_start','index':0,'content_block':{'type':'text','text':text}},{'type':'message_delta','delta':{'stop_reason':reason}},{'type':'message_stop'}]
   return io.BytesIO(b''.join(('data: '+json.dumps(e)+'\n').encode() for e in events))
  c=Anthropic('anthropic',{},None)
  with patch.object(c,'headers',return_value={}),patch('urllib.request.urlopen',side_effect=[stream('first','max_tokens'),stream('last','end_turn')]) as request:
   self.assertEqual(c.run('test','.','model',None,Control(0,lambda _:True,lambda *_:None)),'first\nlast')
   self.assertEqual(request.call_count,2)

 def test_claude_sdk_has_no_turn_cap(self):
  class Captured(Exception):pass
  def client(*,options):
   self.assertIsNone(options.max_turns)
   raise Captured()
  c=ClaudeCode('claude-code',{},None)
  with patch.object(c,'auth_cli',return_value='claude.exe'),patch('claude_agent_sdk.ClaudeSDKClient',side_effect=client):
   with self.assertRaises(Captured):c.run('test','.','',None,Control(0,lambda _:True,lambda *_:None))

 def test_long_user_duration_and_large_plan_are_accepted(self):
  f=test_core.CoreTests();f.setUp()
  try:
   id=f.engine.create({'conversation_id':f.conversation,'timeout_seconds':86400,'steps':[{'connector':'alpha','instruction':'test','depends_on':[]} for _ in range(70)]})
   self.assertEqual(len(f.service.mission(id)['steps']),70)
   f.store.execute("UPDATE missions SET status='failed' WHERE id=?",(id,))
   with patch.object(f.engine,'launch',return_value=id):f.engine.retry(id,True,timeout_seconds=172800)
   self.assertEqual(f.service.mission(id)['spec']['timeout_seconds'],172800)
  finally:f.tearDown()
