import io,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from cyai.connectors import Control,Cancelled,registry,executable
from cyai.extra_connectors import HeadlessCLI,OpenRouter,cli_events

class ExtraTests(unittest.TestCase):
 def control(self):
  self.events=[]
  return Control(0,lambda _:True,lambda *args:self.events.append(args))
 def test_registry_defaults_disabled(self):
  values=registry({},None)
  for key in ('command-code','codebuddy','antigravity','devin','openrouter'):self.assertFalse(values[key].config['enabled'])
 def test_codebuddy_stream_and_resume(self):
  c=HeadlessCLI('codebuddy',{},None);control=self.control();control.mcp_servers={'test':{'command':'test'}}
  def stream(args,root,ctl,text):
   self.assertIn('--resume',args);self.assertIn('old',args)
   conf=Path(args[args.index('--mcp-config')+1]);self.assertEqual(json.loads(conf.read_text())['mcpServers'],control.mcp_servers)
   self.assertEqual(json.loads(text)['message']['content'][0]['text'],'hello')
   yield json.dumps({'type':'system','session_id':'new'})
   yield json.dumps({'type':'assistant','message':{'content':[{'type':'text','text':'answer'}]}})
   yield json.dumps({'type':'result','subtype':'success','result':'answer'})
  with patch.object(c,'command',return_value=['cli']),patch('cyai.extra_connectors.cli_events',side_effect=stream):self.assertEqual(c.run('hello','.','model','old',control),'answer')
  self.assertIn(('session',{'native_id':'new'}),self.events)
 def test_commandcode_native_turn_limit_resumes(self):
  c=HeadlessCLI('command-code',{},None);calls=[]
  def stream(args,*rest):
   calls.append(args)
   yield json.dumps({'type':'result','subtype':'max_turns' if len(calls)==1 else 'success','sessionId':'saved','finalText':'done'})
  with patch.object(c,'command',return_value=['cli']),patch('cyai.extra_connectors.cli_events',side_effect=stream):self.assertEqual(c.run('hello','.','',None,self.control()),'done')
  self.assertEqual(calls[1][-2:],['--resume','saved'])
 def test_antigravity_error_is_not_success(self):
  c=HeadlessCLI('antigravity',{},None)
  with patch.object(c,'command',return_value=['cli']),patch('cyai.extra_connectors.cli_events',return_value=iter([json.dumps({'event':'result','result':{'status':'ERROR','error':'denied'}})])):
   with self.assertRaisesRegex(RuntimeError,'denied'):c.run('hello','.','',None,self.control())
 def test_missing_result_is_error(self):
  c=HeadlessCLI('codebuddy',{},None)
  with patch.object(c,'command',return_value=['cli']),patch('cyai.extra_connectors.cli_events',return_value=iter([])):
   with self.assertRaisesRegex(RuntimeError,'sans résultat'):c.run('hello','.','',None,self.control())
 def test_real_process_and_cancel(self):
  self.assertEqual(''.join(cli_events([sys.executable,'-c','import sys; print(sys.stdin.read())'],'.',self.control(),'hello')).strip(),'hello')
  control=self.control();control.cancelled.set()
  with self.assertRaises(Cancelled):list(cli_events([sys.executable,'-c','import time; time.sleep(30)'],'.',control,''))
 def test_openrouter_images_and_tools(self):
  control=self.control();control.images=[{'mime':'image/png','data':'YWJj'}]
  c=OpenRouter('openrouter',{},None)
  def response(req,**kw):
   data=json.loads(req.data);self.assertEqual(data['model'],'model');self.assertEqual(data['messages'][0]['content'][1]['image_url']['url'],'data:image/png;base64,YWJj');self.assertTrue(data['tools'])
   return io.BytesIO(b'data: {"choices":[{"delta":{"content":"ok"},"finish_reason":"stop"}]}\n\ndata: [DONE]\n')
  with patch.object(c,'headers',return_value={}),patch('urllib.request.urlopen',side_effect=response):self.assertEqual(c.run('hello','.','model',None,control),'ok')
 def test_npm_shim_without_shell(self):
  with tempfile.TemporaryDirectory() as folder:
   base=Path(folder);shim=base/'codebuddy.cmd';shim.touch();pkg=base/'node_modules'/'@tencent-ai'/'codebuddy-code';pkg.mkdir(parents=True);(pkg/'cli.js').touch();(pkg/'package.json').write_text(json.dumps({'bin':{'codebuddy':'cli.js'}}))
   with patch('cyai.connectors.shutil.which',side_effect=lambda key:str(shim) if key=='codebuddy' else 'node.exe'):self.assertEqual(executable('codebuddy'),['node.exe',str((pkg/'cli.js').resolve())])

class LargeTransportTests(unittest.TestCase):
 def test_real_stdin_large_unicode_integrity(self):
  import hashlib
  prompt='début\n'+('é漢字 ligne 0123456789\n'*26000)+'FIN'
  control=Control(0,lambda _:True,lambda *args:None)
  code="import sys,hashlib; sys.stdin.reconfigure(encoding='utf-8'); s=sys.stdin.read(); print(hashlib.sha256(s.encode('utf-8')).hexdigest())"
  self.assertEqual(''.join(cli_events([sys.executable,'-c',code],'.',control,prompt)).strip(),hashlib.sha256(prompt.encode('utf-8')).hexdigest())
 def test_antigravity_denied_actions_label_and_full_prompt(self):
  prompt='START'+('abc123 '*70000)+'END'
  c=HeadlessCLI('antigravity',{},None)
  def stream(args,root,control,text):
   self.assertEqual(json.loads(text)['message']['content'],prompt)
   yield json.dumps({'event':'result','result':{'status':'SUCCESS','denied_actions':['run_command']}})
  with patch.object(c,'command',return_value=['cli']),patch('cyai.extra_connectors.cli_events',side_effect=stream):
   with self.assertRaisesRegex(RuntimeError,'Actions refusées.*run_command'):
    c.run(prompt,'.','model',None,Control(0,lambda _:True,lambda *args:None))
