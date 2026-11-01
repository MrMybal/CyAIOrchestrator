import json, unittest
from unittest.mock import Mock,patch
from cyai.local_tools import run
class LocalMCPTests(unittest.TestCase):
 def response(self,events,ollama=False):
  r=Mock();r.__enter__=Mock(return_value=[(json.dumps(e)+'\n').encode() if ollama else ('data: '+(e if isinstance(e,str) else json.dumps(e))+'\n').encode() for e in events]);r.__exit__=Mock(return_value=False);return r
 def test_openai_fragmented_calls(self):
  c=Mock();c.benchmark=False;c.images=[];first=[{'choices':[{'delta':{'tool_calls':[{'index':0,'id':'t','function':{'name':'cyai_call','arguments':'{"action":'}}]}}]},{'choices':[{'delta':{'tool_calls':[{'index':0,'function':{'arguments':'"local_state"}'}}]},'finish_reason':'tool_calls'}]},'[DONE]'];last=[{'choices':[{'delta':{'content':'OK'},'finish_reason':'stop'}]},'[DONE]']
  with patch('urllib.request.urlopen',side_effect=[self.response(first),self.response(last)]) as request:
   c.plugin_call.return_value={'ok':True};self.assertEqual(run('http://localhost',{},'test',c),'OK');c.plugin_call.assert_called_once_with('cyai_call',{'action':'local_state'});self.assertEqual(json.loads(request.call_args[0][0].data)['messages'][-1]['tool_call_id'],'t')
 def test_interruption_never_executes(self):
  c=Mock();c.benchmark=False;c.images=[]
  with patch('urllib.request.urlopen',return_value=self.response([{'choices':[{'delta':{'tool_calls':[{'index':0,'function':{'name':'cyai_actions','arguments':'{}'}}]}}]}])):
   with self.assertRaises(RuntimeError):run('http://localhost',{},'test',c)
  c.plugin_call.assert_not_called()
 def test_ollama_tools(self):
  c=Mock();c.benchmark=False;c.images=[];c.plugin_call.return_value={'isError':True,'content':'denied'}
  with patch('urllib.request.urlopen',side_effect=[self.response([{'message':{'tool_calls':[{'function':{'name':'cyai_actions','arguments':{}}}]},'done':True}],True),self.response([{'message':{'content':'Denied'},'done':True}],True)]):
   self.assertEqual(run('http://localhost',{},'test',c,ollama=True),'Denied');c.plugin_call.assert_called_once_with('cyai_actions',{})
