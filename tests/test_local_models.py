import io
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from cyai.local_models import LocalModels, download, runtime_args
from cyai.benchmarks import parse_aider, matching


class LocalModelTests(unittest.TestCase):
    def test_queue_serializes_deduplicates_and_survives_failure(self):
        import threading,time
        gate=threading.Event();started=threading.Event();finished=threading.Event();order=[]
        service=SimpleNamespace(engine=SimpleNamespace(connectors={'local':SimpleNamespace(config={})},secrets=SimpleNamespace(redact=lambda x:x)),store=SimpleNamespace(log=lambda *a:None))
        manager=LocalModels(service)
        def first(progress):
            started.set();gate.wait(3);order.append('first');raise ValueError('download failed')
        a=manager.job('first',first);self.assertTrue(started.wait(1))
        b=manager.job('second',lambda p:(order.append('second'),finished.set()))
        self.assertEqual(manager.jobs[b['job_id']]['status'],'queued')
        self.assertEqual(manager.job('second',lambda p:None)['job_id'],b['job_id'])
        gate.set();self.assertTrue(finished.wait(2))
        for _ in range(100):
            if not manager.worker_active:break
            time.sleep(.01)
        self.assertEqual(order,['first','second'])
        self.assertEqual(manager.jobs[a['job_id']]['status'],'failed')
        self.assertEqual(manager.jobs[b['job_id']]['status'],'succeeded')
        self.assertFalse(manager.worker_active)

    def test_model_overrides_preserve_global_defaults_and_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = {'device':'cpu','threads':4,'context':4096,'models':[{'id':'one','path':str(Path(tmp)/'one.gguf')}]}
            service = SimpleNamespace(engine=SimpleNamespace(connectors={'local':SimpleNamespace(config=config)}),
                config={}, plugins=SimpleNamespace(persist=lambda:None),components=SimpleNamespace(state=lambda:[]),store=SimpleNamespace(path=Path(tmp)/'db'))
            manager = LocalModels(service)
            manager.action('local_model_settings',{'id':'one','settings':{'device':'hybrid','gpu_layers':12,'context':8192}})
            result = manager.state()['models'][0]['effective_settings']
            self.assertEqual(result, {'device':'hybrid','gpu_layers':12,'threads':4,'context':8192})
            self.assertEqual(config['context'],4096)
            manager.action('local_model_settings',{'id':'one','settings':{}})
            self.assertEqual(manager.state()['models'][0]['effective_settings']['context'],4096)
            with self.assertRaises(ValueError):
                manager.action('local_model_settings',{'id':'one','settings':{'context':-2}})

    def test_device_controls(self):
        for device, expected in [('cpu', '0'), ('gpu', '999'), ('hybrid', '12')]:
            args = runtime_args('server', 'model', {'device': device, 'gpu_layers': 12}, 1234, 'secret')
            self.assertEqual(args[args.index('--n-gpu-layers') + 1], expected)
            self.assertEqual(args[args.index('--host') + 1], '127.0.0.1')
        with self.assertRaises(ValueError):
            runtime_args('server', 'model', {'context': -1}, 1234, 'secret')

    def test_failed_digest_never_publishes_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / 'model.gguf'
            response = io.BytesIO(b'GGUFcorrupt')
            response.headers = {'Content-Length': '11'}
            with patch('urllib.request.urlopen', return_value=response):
                with self.assertRaisesRegex(ValueError, 'SHA-256'):
                    download('https://example.test/model', target, lambda *_: None, 'a' * 64)
            self.assertFalse(target.exists())
            self.assertFalse(target.with_suffix('.gguf.part').exists())

    def test_benchmark_variants_are_not_fuzzy_matched(self):
        rows = parse_aider('- name: test\n  model: model-v1 (high)\n  pass_rate_2: 71.5\n  date: 2025-01-01\n')
        self.assertEqual(rows[0]['score'], 71.5)
        self.assertEqual(matching(rows, 'model-v1'), [])
        self.assertEqual(len(matching(rows, 'model-v1 (high)')), 1)
        with self.assertRaises(ValueError):
            parse_aider('an incompatible publisher format')

    def test_unload_waits_for_process_and_preserves_models(self):
        from unittest.mock import Mock
        model={'id':'one','path':'kept.gguf'}
        config={'models':[model]}
        service=SimpleNamespace(engine=SimpleNamespace(connectors={'local':SimpleNamespace(config=config)}))
        manager=LocalModels(service);proc=Mock();proc.poll.return_value=0
        manager.proc=proc;manager.loaded='one';manager.base='http://localhost';manager.key='secret'
        with patch('cyai.local_models.stop_process') as stop:
            self.assertEqual(manager.action('local_stop',{}),{'ok':True})
            stop.assert_called_once_with(proc);proc.wait.assert_called_once()
        self.assertIsNone(manager.proc);self.assertIsNone(manager.loaded)
        self.assertEqual(manager.key,'');self.assertEqual(config['models'],[model])

    def test_unload_does_not_interrupt_inference(self):
        service=SimpleNamespace(engine=SimpleNamespace(connectors={'local':SimpleNamespace(config={})}))
        manager=LocalModels(service);manager.inference_lock.acquire()
        try:
            with patch('cyai.local_models.stop_process') as stop:
                with self.assertRaisesRegex(ValueError,'conversation'):manager.action('local_stop',{})
                stop.assert_not_called()
        finally:manager.inference_lock.release()
