import threading,time,unittest
from types import SimpleNamespace
from unittest.mock import patch
from cyai.connectors import NativeLocal,Control,Cancelled
from cyai.resource_usage import parse_windows_gpu
from cyai.local_tools import normalized_usage

class InferenceControlTests(unittest.TestCase):
 def test_cancel_interrupts_blocked_http_before_first_token(self):
  entered=threading.Event();released=threading.Event();errors=[]
  manager=SimpleNamespace(inference_lock=threading.Lock(),start=lambda *a:None,base='http://localhost',key='test',stop=lambda:released.set())
  connector=NativeLocal('local',{},None);connector.manager=manager
  control=Control(0,lambda _:False,lambda *a:None)
  def blocked(*a,**kw):
   entered.set();released.wait(3);raise OSError('closed stream')
  def run():
   try:connector.run('test','.',None,None,control)
   except Exception as e:errors.append(e)
  with patch('urllib.request.urlopen',side_effect=blocked):
   worker=threading.Thread(target=run);worker.start();self.assertTrue(entered.wait(1))
   control.cancelled.set();worker.join(2)
  self.assertFalse(worker.is_alive());self.assertIsInstance(errors[0],Cancelled)
  self.assertFalse(manager.inference_lock.locked());self.assertIsNone(manager.active_control)
 def test_wddm_aggregates_devices_without_total_instance(self):
  self.assertEqual(parse_windows_gpu([{'Name':'pid_42_luid_a_phys_0','DedicatedUsage':100},{'Name':'pid_42_luid_b_phys_1','DedicatedUsage':20},{'Name':'_Total','DedicatedUsage':120}]),{42:120})
  with self.assertRaises(ValueError):parse_windows_gpu(None)
 def test_openai_usage_normalization(self):
  self.assertEqual(normalized_usage({'prompt_tokens':17,'completion_tokens':9})['input_tokens'],17)
  self.assertEqual(normalized_usage({'prompt_tokens':17,'completion_tokens':9})['output_tokens'],9)

 def test_unload_cancels_active_control(self):
  from cyai.local_models import LocalModels
  manager=LocalModels(SimpleNamespace(engine=SimpleNamespace(connectors={'local':SimpleNamespace(config={})})))
  manager.active_control=Control(0,None,None)
  manager.inference_lock.acquire()
  try:
   self.assertEqual(manager.action('local_stop',{}),{'ok':True})
   self.assertTrue(manager.active_control.cancelled.is_set())
  finally:manager.inference_lock.release()
