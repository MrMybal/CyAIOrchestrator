import unittest,tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from cyai.connectors import NativeLocal
class LocalStatusTests(unittest.TestCase):
 def test_readiness_and_process_changes(self):
  with tempfile.TemporaryDirectory() as tmp:
   runtime=Path(tmp)/'server.exe';runtime.touch();model=Path(tmp)/'model.gguf';model.touch()
   c=NativeLocal('local',{'runtime':str(runtime),'models':[]},None)
   self.assertEqual(c.check()['status'],'unconfigured')
   c.config['models']=[{'id':'tiny','name':'Tiny','path':str(model)}]
   self.assertEqual(c.check()['status'],'ready')
   c.manager=SimpleNamespace(proc=Mock(),loaded='tiny');c.manager.proc.poll.return_value=None
   self.assertEqual(c.check()['status'],'running')
   c.manager.proc.poll.return_value=1
   self.assertEqual(c.check()['status'],'ready')
   model.unlink();self.assertEqual(c.check()['status'],'unconfigured')
if __name__=='__main__':unittest.main()
