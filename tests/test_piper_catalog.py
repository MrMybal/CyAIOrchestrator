import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from cyai import piper_catalog
from cyai.voice import Voice
import test_core


class PiperCatalogTests(unittest.TestCase):
    def test_official_french_variants_and_named_speakers(self):
        items = {v['id']: v for v in piper_catalog.load()}
        self.assertEqual(len([k for k in items if k.startswith('fr_FR-')]), 7)
        self.assertEqual(set(items['fr_FR-mls-medium']['speakers'].values()), set(range(125)))
        self.assertEqual(items['fr_FR-upmc-medium']['speakers'], {'jessica': 0, 'pierre': 1})
        self.assertTrue(items['fr_FR-mls_1840-low']['file'].endswith('.onnx'))

    def test_refresh_validates_then_keeps_offline_copy_on_failure(self):
        doc = json.loads(piper_catalog.BUNDLED.read_text(encoding='utf8'))
        with tempfile.TemporaryDirectory() as folder:
            cache = Path(folder) / 'catalog.json'
            with patch('cyai.connectors.request_json', side_effect=[{'sha': doc['revision']}, doc['voices']]):
                self.assertEqual(len(piper_catalog.refresh(cache)), 177)
            before = cache.read_bytes()
            broken = copy.deepcopy(doc['voices'])
            first = next(iter(broken.values()))
            first['files'] = {'../evil.onnx': {'md5_digest': 'a'*32}}
            with patch('cyai.connectors.request_json', side_effect=[{'sha': doc['revision']}, broken]):
                with self.assertRaises(ValueError): piper_catalog.refresh(cache)
            self.assertEqual(cache.read_bytes(), before)
            self.assertEqual(len(piper_catalog.load(cache)), 177)

    def test_md5_rejects_corruption(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'model'; path.write_bytes(b'good')
            piper_catalog.verify_md5(path, hashlib.md5(b'good').hexdigest())
            path.write_bytes(b'bad')
            with self.assertRaises(ValueError): piper_catalog.verify_md5(path, hashlib.md5(b'good').hexdigest())

    def test_all_mls_speakers_visible_after_single_model_install(self):
        fixture = test_core.CoreTests(); fixture.setUp()
        try:
            voice = fixture.service.voice
            model = fixture.scratch / 'mls.onnx' if hasattr(fixture, 'scratch') else fixture.service.store.path.parent / 'mls.onnx'
            model.write_bytes(b'fixture')
            fixture.service.config['voice'] = {'installed': {'fr_FR-mls-medium': {'path': str(model)}}, 'runtimes': {'piper': {'path': str(model)}}}
            voice.windows_list = []
            with patch.object(voice.python_envs, 'installed', return_value=False):
                choices = [v for v in voice.voices() if v['key'].startswith('piper:fr_FR-mls-medium:')]
            self.assertEqual(len(choices), 125)
            self.assertEqual({v['key'].rsplit(':', 1)[1] for v in choices}, {str(n) for n in range(125)})
        finally: fixture.tearDown()
