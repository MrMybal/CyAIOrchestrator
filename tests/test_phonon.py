import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import test_core
from cyai.voice_phonon import PhononSTT
from cyai.voice import voice_action

class PhononTests(unittest.TestCase):
 def setUp(self):
  self.fixture=test_core.CoreTests();self.fixture.setUp();self.voice=self.fixture.service.voice
  self.voice.windows_list=[]
 def tearDown(self):
  self.voice.shutdown();self.fixture.tearDown()
 def test_settings_and_french_model_selection(self):
  self.voice.save_settings({'stt':{'engine':'phonon','phonon_model':'phonon-2.5','language':'fr'}})
  with patch.object(self.voice.python_envs,'installed',return_value=True):
   self.assertTrue(self.voice.stt_status()['ready'])
   self.assertEqual(self.voice._stt(self.voice.settings()).model,'phonon-2.5')
  self.voice.save_settings({'stt':{'phonon_model':'phonon-2'}})
  self.assertIn('anglais uniquement',self.voice.stt_status()['reason'])
  with self.assertRaises(ValueError):self.voice.save_settings({'stt':{'phonon_model':'untrusted'}})
 def test_transcript_wav_cleanup_and_truncation(self):
  env=SimpleNamespace(python=lambda e:sys.executable,worker=lambda e:'worker',env_dir=lambda e:Path.cwd(),worker_env=lambda:{})
  seen=[]
  class Worker:
   def __init__(self,*a):pass
   def alive(self):return True
   def send(self,data):
    seen.append(Path(data['file']));assert seen[-1].read_bytes().startswith(b'RIFF')
   def next(self,n):return {'ok':True,'text':'Bonjour','truncated':len(seen)>1}
   def close(self):pass
  with patch('cyai.voice_python._Worker',Worker):
   engine=PhononSTT(env)
   self.assertEqual(engine.transcribe(b'\0'*1600,'fr'),'Bonjour')
   self.assertFalse(seen[-1].exists())
   with self.assertRaisesRegex(RuntimeError,'incomplète'):engine.transcribe(b'\0'*1600,'fr')
   self.assertFalse(seen[-1].exists());engine.close()
 def test_slow_windows_discovery_does_not_hold_settings(self):
  import threading
  done=threading.Event()
  windows=SimpleNamespace(voices=lambda:(done.wait(2),[])[1],close=lambda:None)
  self.voice.windows_list=None
  with patch.object(self.voice,'_windows',return_value=windows),patch('cyai.model_memory.hardware',return_value={}):
   self.voice.audio=SimpleNamespace(inputs=lambda:[],outputs=lambda:[])
   start=time.monotonic();result=voice_action(self.fixture.service,'voice_settings',{})
   self.assertLess(time.monotonic()-start,1)
   self.assertTrue(result['windows_pending'])
   done.set()
