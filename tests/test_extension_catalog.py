import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

from cyai.extension_catalog import CATALOG, ExtensionCatalog, extract_archive, legacy_replacement
from cyai.cytool_discovery import discover
from cyai.plugins import Plugins


class ExtensionCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name).resolve()
        self.secret_values={}
        self.service=SimpleNamespace(config={},config_path=self.root/'config.json',store=SimpleNamespace(path=self.root/'db.sqlite3'),
            engine=SimpleNamespace(lock=threading.RLock(),secrets=SimpleNamespace(get=lambda k:self.secret_values.get(k),set=lambda k,v:self.secret_values.update({k:v}))))
        self.service.plugins=Plugins(self.service)
        self.manager=ExtensionCatalog(self.service)
    def tearDown(self):
        self.service.plugins.close_cytools()
        self.tmp.cleanup()
    def manifest(self):
        return {'schemaVersion':1,'protocolVersion':'1.0','id':'cy.tool.aichat','name':'CyTools_AIChat','version':'0.2.0','interfaces':['MCP'],'executable':'NEVER EXECUTE'}
    def archive(self,manifest=None):
        p=self.root/'portable.zip'
        with zipfile.ZipFile(p,'w') as z:
            z.writestr('CyTools_AIChat/app/CyTool.json',json.dumps(manifest or self.manifest()))
            z.writestr('CyTools_AIChat/app/tool.py','raise RuntimeError("detection must not execute code")')
            z.writestr('CyTools_AIChat/runtime/python/python.exe',b'not executed')
        return p
    def test_catalog_state_is_offline_and_does_not_install_or_start_tools(self):
        with patch('urllib.request.urlopen',side_effect=AssertionError('no network')):
            entries=self.manager.state()
        self.assertEqual(len(entries),10)
        self.assertEqual(sum(e['kind']=='tool' for e in entries),6)
        self.assertFalse(self.manager.folder().exists())
        self.assertNotIn('cyprojectcodex',self.service.config['plugins'])
        self.assertFalse(self.service.config['plugins']['cytask']['enabled'])
    def test_legacy_detection_preserves_custom_and_current_tools(self):
        self.assertEqual(legacy_replacement({'cytools':True,'name':'CyTools_Piper_TTS'}),'audiostudio')
        self.assertEqual(legacy_replacement({'cytools':True,'cytools_id':'cy.tool.autoremesher'}),'meshstudio')
        self.assertEqual(legacy_replacement({'cytools':True,'name':'CyTools_MeshStudio'}),'')
        self.assertEqual(legacy_replacement({'cytools':True,'name':'My own tool'}),'')
    def test_current_portable_and_source_folders_are_detected_without_side_effects(self):
        root=self.root/'portable';(root/'app').mkdir(parents=True)
        (root/'app/CyTool.json').write_text(json.dumps(self.manifest()))
        (root/'app/tool.py').write_text('raise RuntimeError("do not execute")')
        python=root/'runtime/python/python.exe';python.parent.mkdir(parents=True);python.write_bytes(b'fake')
        for folder in (root,root/'app'):
            result=discover(str(folder))
            self.assertEqual(result['command'],str(python))
            self.assertEqual(result['args'],[str(root/'app/tool.py'),'--data-dir',str(root/'data/jobs-cyai'),'mcp'])
            self.assertEqual(result['source_repo'],'CyTools_AIChat')
            self.assertEqual(result['warnings'],[])
        self.assertFalse((root/'data').exists())
    def test_invalid_archives_are_rejected_before_any_files_are_written(self):
        for bad in ('../escape','C:/escape','app\\escape'):
            target=self.root/'unpacked';target.mkdir(exist_ok=True)
            archive=self.root/'bad.zip'
            # ZipInfo normally normalizes Windows separators; retain the raw hostile member name.
            info=zipfile.ZipInfo();info.filename=bad
            with zipfile.ZipFile(archive,'w') as z:z.writestr('first.txt','text');z.writestr(info,'bad')
            with self.subTest(bad=bad),self.assertRaises(ValueError):extract_archive(archive,target)
            self.assertEqual(list(target.iterdir()),[])
        with zipfile.ZipFile(archive,'w') as z:z.writestr('App/file','one');z.writestr('app/FILE','two')
        with self.assertRaises(ValueError):extract_archive(archive,target)
    def test_release_selects_portable_not_app_patch_and_requires_published_digest(self):
        release={'tag_name':'v0.2.0','assets':[
            {'name':'CyTools_AIChat-0.2.0-app.zip'},
            {'name':'CyTools_AIChat-0.2.0-windows-x64.zip','size':123,'digest':'sha256:'+'a'*64,'browser_download_url':'https://github.com/MrMybal/CyTools_AIChat/releases/download/v0.2.0/tool.zip'}]}
        with patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(release).encode())):
            result=self.manager.check_one('aichat')
        self.assertIn('windows-x64',result['asset']['name'])
        release['assets'][1].pop('digest')
        with patch('urllib.request.urlopen',return_value=io.BytesIO(json.dumps(release).encode())):
            self.assertIsNone(self.manager.check_one('aichat')['asset'])
    def test_install_isolated_portable_registers_mcp_and_updates_keep_bindings(self):
        archive=self.archive()
        digest='sha256:'+hashlib.sha256(archive.read_bytes()).hexdigest()
        info={'version':'v0.2.0','asset':{'name':'CyTools_AIChat-0.2.0-windows-x64.zip','digest':digest,'size':archive.stat().st_size,'browser_download_url':'https://github.com/MrMybal/CyTools_AIChat/releases/download/v0.2.0/file.zip'}}
        self.service.config['extension_releases']={'aichat':info}
        def fetch(url,target,progress,expected):
            self.assertEqual(expected,digest);target.write_bytes(archive.read_bytes())
        with patch('cyai.extension_catalog.download',side_effect=fetch),patch('subprocess.Popen',side_effect=AssertionError('must not launch')):
            self.manager._install(self.manager.entry('aichat'),Mock())
        p=next(p for p in self.service.config['plugins'].values() if p.get('cytools_id')=='cy.tool.aichat')
        self.assertTrue(Path(p['command']).is_file())
        self.assertEqual(p['version'],'0.2.0')
        p['projects']={'one':{'enabled':False}};p['enabled']=False
        with patch('subprocess.Popen',side_effect=AssertionError('must not launch')):
            self.manager._install(self.manager.entry('aichat'),Mock())
        current=self.service.config['plugins'][p['id']]
        self.assertFalse(current['enabled']);self.assertEqual(current['projects'],{'one':{'enabled':False}})
    def test_wrong_tool_in_release_never_replaces_existing_registration(self):
        archive=self.archive({**self.manifest(),'id':'cy.tool.wrong'})
        asset={'name':'bad-windows-x64.zip','digest':'sha256:'+hashlib.sha256(archive.read_bytes()).hexdigest(),'size':archive.stat().st_size,'browser_download_url':'unused'}
        self.service.config['extension_releases']={'aichat':{'version':'v0.2.0','asset':asset}}
        original=copy.deepcopy(self.service.config['plugins'])
        with patch('cyai.extension_catalog.download',side_effect=lambda u,p,*a:p.write_bytes(archive.read_bytes())):
            with self.assertRaisesRegex(ValueError,'Identifiant'):self.manager._install(self.manager.entry('aichat'),Mock())
        self.assertEqual(self.service.config['plugins'],original)
        self.assertFalse(list((self.manager.folder()/'aichat').glob('staging-*')))
    def test_cytask_token_import_is_vaulted_and_injected_only_into_process(self):
        p=copy.deepcopy(self.service.config['plugins']['cytask'])
        imported={'mcpServers':{'cytask':{'command':'node','args':p['args'],'env':{'CYTASK_URL':'http://127.0.0.1:8080','CYTASK_TOKEN':'test'}}}}
        self.service.plugins.save({'manifest':p,'mcp_config':json.dumps(imported)})
        saved=self.service.config['plugins']['cytask']
        self.assertNotIn('CYTASK_TOKEN',saved['env'])
        self.assertEqual(self.secret_values['plugin:cytask'],'test')
        self.assertEqual(self.service.plugins.process_env(saved)['CYTASK_TOKEN'],'test')
        self.assertNotIn('CYTASK_TOKEN',json.loads(self.service.config_path.read_text('utf-8'))['plugins']['cytask']['env'])
    def test_existing_codex_connection_keeps_scope_and_gains_current_read_tools(self):
        config={'plugins':{'cyaicodex':{'id':'cyaicodex','type':'mcp','name':'Personal','enabled':True,'transport':'http','url':'http://127.0.0.1:8765/mcp','projects':{'one':{'enabled':False}},'read_tools':['get_context','search_methods','get_method']}}}
        self.service.config=config
        plugins=Plugins(self.service)
        p=plugins.config['plugins']['cyaicodex']
        self.assertTrue(p['enabled']);self.assertEqual(p['projects'],{'one':{'enabled':False}})
        self.assertTrue({'search_skills','get_skill','view_image'}<=set(p['read_tools']))
        self.assertNotIn('create_skill',p['read_tools'])
        self.assertEqual(plugins.web_url('cyaicodex')['url'],'http://127.0.0.1:8765/')
    def test_codex_image_result_survives_read_adapter(self):
        self.service.config['plugins']['cyaicodex']['enabled']=True
        result={'content':[{'type':'image','mimeType':'image/png','data':'A'*120000}]}
        with patch.object(self.service.plugins,'rpc',return_value=result):
            self.assertEqual(self.service.plugins.read('cyaicodex',None,'view_image',{}),result)
