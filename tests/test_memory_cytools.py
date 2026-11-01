import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from cyai.model_memory import estimate, gguf_estimate
from cyai.plugins import Plugins
from cyai.local_models import LocalModels

class MemoryCyToolsTests(unittest.TestCase):
 def test_memory_advisory_uses_free_not_only_total(self):
  self.assertTrue(estimate('fish:default',{'gpu_total_gib':24,'gpu_free_gib':10})['warning'])
  self.assertFalse(estimate('qwen:custom:Ryan',{'gpu_total_gib':24,'gpu_free_gib':22})['warning'])
  self.assertEqual('danger',estimate('fish:default',{'gpu_total_gib':8,'gpu_free_gib':8})['severity'])
  self.assertEqual('warning',estimate('qwen:design',{})['severity'])
  self.assertFalse(estimate('pocket:french:eve',{})['warning'])
 def test_bonsai_family_preserves_other_models(self):
  self.assertEqual(LocalModels.runtime_family({'name':'Bonsai 2 27B PTQ1_0'}),'prism')
  self.assertEqual(LocalModels.runtime_family({'path':'prism-ml--Ternary-Bonsai-2-27B.gguf'}),'prism')
  self.assertEqual(LocalModels.runtime_family({'name':'Qwen3.5 27B'}),'standard')
 def test_import_does_not_execute_manifest_command(self):
  with tempfile.TemporaryDirectory() as tmp:
   service=SimpleNamespace(config={},config_path=Path(tmp)/'config.json')
   plugins=Plugins(service)
   manifest={'schemaVersion':1,'protocolVersion':'1.0','id':'cy.test','name':'Test','interfaces':['MCP'],'executable':'UNTRUSTED'}
   plugins.import_cytool({'manifest':manifest,'command':'python','args':['tool.py','mcp'],'cwd':tmp})
   entry=next(p for p in service.config['plugins'].values() if p.get('cytools'))
   self.assertEqual(entry['command'],'python')
   self.assertNotIn('op_echo',entry['read_tools'])
   self.assertIn('cy_get_job',entry['read_tools'])
   with self.assertRaises(ValueError):plugins.import_cytool({'manifest':manifest,'command':'python','args':['tool.py','mcp'],'cwd':tmp})
 def test_prism_install_keeps_standard_runtime(self):
  with tempfile.TemporaryDirectory() as tmp:
   config={'runtime':'standard.exe','backend':'cpu'}
   service=SimpleNamespace(engine=SimpleNamespace(connectors={'local':SimpleNamespace(config=config)}),store=SimpleNamespace(path=Path(tmp)/'db'),config={},plugins=SimpleNamespace(persist=lambda:None))
   manager=LocalModels(service)
   manager.job=lambda name,fn:fn(lambda *a:None)
   release={'tag_name':'prism-test','assets':[{'name':'llama-test-bin-win-cpu-x64.zip','digest':'sha256:abc','browser_download_url':'https://example.test/runtime.zip'}]}
   def archive(url,path,progress,sha):
    import zipfile
    with zipfile.ZipFile(path,'w') as z:z.writestr('llama-server.exe',b'test')
   with patch('cyai.local_models.request_json',return_value=[release]),patch('cyai.local_models.download',side_effect=archive):manager.install_runtime('prism-cpu')
   self.assertEqual(config['runtime'],'standard.exe')
   self.assertTrue(Path(config['prism_runtime']).is_file())
   self.assertTrue((Path(tmp)/'runtimes/prism-runtime.json').is_file())
