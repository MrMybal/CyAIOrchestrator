import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from cyai.optional_components import OptionalComponents


class OptionalComponentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name)
        self.claude = SimpleNamespace(config={}, auth_cli=Mock(side_effect=ValueError('not installed')))
        self.service = SimpleNamespace(store=SimpleNamespace(path=self.folder / 'store.sqlite3'),
            engine=SimpleNamespace(connectors={'claude-code':self.claude}),
            config={}, plugins=SimpleNamespace(persist=Mock()), health={'claude-code':{'status':'unconfigured'}},
            local_models=SimpleNamespace(job=Mock(return_value={'job_id':'test'})))
        self.components = OptionalComponents(self.service)
        self.content = b'0123456789abcdefghijk'
        self.digest = hashlib.sha256(self.content).hexdigest()
        self.addCleanup(patch.stopall)
        patch('cyai.optional_components.FFMPEG_BYTES',len(self.content)).start()
        patch('cyai.optional_components.FFMPEG_SHA256',self.digest).start()
        patch('cyai.optional_components.CHUNK_BYTES',5).start()

    def cache(self, data=None):
        file=self.components.ffmpeg_path();file.parent.mkdir(parents=True,exist_ok=True);file.write_bytes(self.content if data is None else data);return file

    def test_inventory_does_not_download_or_create_cache(self):
        with patch('cyai.optional_components.download') as download:
            items=self.components.state()
        download.assert_not_called();self.assertFalse(self.components.folder().exists());self.assertFalse(any(i['installed'] for i in items))

    def test_existing_native_cli_is_reused(self):
        self.claude.auth_cli=Mock(return_value='installed-claude.exe')
        self.assertTrue(self.components.state()[1]['installed'])

    def test_install_is_explicit_and_uses_the_shared_queue(self):
        self.assertEqual(self.components.install('ffmpeg'),{'job_id':'test'})
        self.service.local_models.job.assert_called_once_with('Composant · ffmpeg',self.components.install_ffmpeg)
        with self.assertRaises(ValueError):self.components.install('../anything')

    def test_absent_video_codec_never_initiates_download(self):
        with patch('cyai.optional_components.download') as download:
            with self.assertRaisesRegex(ValueError,'Téléchargements'):self.components.ffmpeg_asset('ffmpeg-core.wasm.part0')
        download.assert_not_called()

    def test_video_chunking_and_tampered_cache(self):
        file=self.cache()
        self.assertEqual(self.components.ffmpeg_asset('ffmpeg-core.wasm.part0'),self.content[:5])
        self.assertEqual(self.components.ffmpeg_asset('ffmpeg-core.wasm.part3'),self.content[15:20])
        self.assertEqual(self.components.ffmpeg_asset('ffmpeg-core.wasm'),self.content)
        file.write_bytes(b'bad')
        with self.assertRaisesRegex(ValueError,'modifié'):self.components.ffmpeg_asset('ffmpeg-core.wasm')
        with self.assertRaises(ValueError):self.components.ffmpeg_asset('../../store.sqlite3')

    def test_download_verifies_expected_hash_and_activates_atomically(self):
        def download(url,path,progress,expected):
            self.assertEqual(expected,self.digest);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(self.content)
        with patch('cyai.optional_components.download',side_effect=download):self.components.install_ffmpeg(Mock())
        self.assertEqual(self.components.ffmpeg_path().read_bytes(),self.content)
        self.assertFalse(self.components.ffmpeg_path().with_name('ffmpeg-download.wasm').exists())

    def test_failed_download_preserves_the_previous_cache(self):
        old=self.cache(b'previous cache')
        def fail(url,path,*args):
            path.write_bytes(b'partial');raise ValueError('integrity failure')
        with patch('cyai.optional_components.download',side_effect=fail):
            with self.assertRaises(ValueError):self.components.install_ffmpeg(Mock())
        self.assertEqual(old.read_bytes(),b'previous cache')
        self.assertFalse(old.with_name('ffmpeg-download.wasm').exists())

    def test_same_size_corruption_remains_available_for_reinstallation(self):
        file=self.cache()
        self.assertTrue(self.components.state()[0]['installed'])
        stamp=file.stat().st_mtime_ns
        file.write_bytes(b'x'*len(self.content))
        # Some Windows volumes retain the same timestamp for two writes in one tick.
        import os
        os.utime(file,ns=(file.stat().st_atime_ns,stamp+1000000000))
        self.assertFalse(self.components.state()[0]['installed'])

    def test_valid_cache_does_not_redownload(self):
        self.cache()
        with patch('cyai.optional_components.download') as download:self.components.install_ffmpeg(Mock())
        download.assert_not_called()

    def test_native_cli_uses_vendor_manifest_and_persists_its_path(self):
        manifest=json.dumps({'platforms':{'win32-x64':{'checksum':self.digest}}})
        def download(url,path,progress,expected):
            self.assertIn('/1.2.3/win32-x64/claude.exe',url);self.assertEqual(expected,self.digest)
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(self.content)
        with patch('cyai.optional_components.platform.system',return_value='Windows'), patch('cyai.optional_components.platform.machine',return_value='AMD64'), patch('cyai.optional_components.read_text',side_effect=['1.2.3',manifest]), patch('cyai.optional_components.download',side_effect=download):
            self.components.install_claude(Mock())
        file=Path(self.claude.config['executable']);self.assertEqual(file.read_bytes(),self.content)
        self.assertEqual(self.service.config['connectors']['claude-code']['executable'],str(file));self.service.plugins.persist.assert_called_once()
        self.assertNotIn('claude-code',self.service.health)

    def test_native_cli_rejects_untrusted_version_or_missing_checksum(self):
        for replies in [['../bad'],['1.2.3','{}']]:
            with patch('cyai.optional_components.platform.system',return_value='Windows'), patch('cyai.optional_components.read_text',side_effect=replies), patch('cyai.optional_components.download') as download:
                with self.assertRaises(ValueError):self.components.install_claude(Mock())
            download.assert_not_called()
        self.assertNotIn('executable',self.claude.config)
