import hashlib,json,sys,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'packaging'))
from release_install import install_package,rollback,read_install
from cyai.launch_config import resolve_config

class ReleaseTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.base=Path(self.tmp.name).resolve();self.root=self.base/'app';self.home=self.base/'user';self.config=self.base/'config.json';self.config.write_text('{"data_dir":"kept"}');self.launcher=self.base/'launcher.exe';self.launcher.write_bytes(b'launcher')
 def tearDown(self):self.tmp.cleanup()
 def package(self,version,files=None):
  files=files or {'CyAIOrchestrator.exe':version.encode()};z=self.base/'payload.zip';m=self.base/'manifest.json'
  with zipfile.ZipFile(z,'w') as out:
   for name,data in files.items():out.writestr(name,data)
  m.write_text(json.dumps({'version':version,'files':{n:{'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in files.items()}}));return z,m
 def install(self,version):return install_package(*self.package(version),self.root,self.config,self.home,self.launcher)
 def test_install_upgrade_and_rollback_preserve_data(self):
  first=self.install('0.2.0');second=self.install('0.2.1');self.assertEqual(second['previous'],first['current']);self.assertEqual(self.config.read_text(),'{"data_dir":"kept"}');rollback(self.root);self.assertEqual(read_install(self.root)['current'],first['current']);self.assertTrue((self.root/second['current']/'CyAIOrchestrator.exe').exists())
 def test_corrupt_package_keeps_current(self):
  first=self.install('0.2.0');z,m=self.package('0.2.1');data=json.loads(m.read_text());data['files']['CyAIOrchestrator.exe']['sha256']='wrong';m.write_text(json.dumps(data))
  with self.assertRaisesRegex(ValueError,'SHA-256'):install_package(z,m,self.root,self.config,self.home,self.launcher)
  self.assertEqual(read_install(self.root),first)
 def test_traversal_rejected(self):
  z,m=self.package('0.2.0',{'CyAIOrchestrator.exe':b'x','../outside':b'x'})
  with self.assertRaises(ValueError):install_package(z,m,self.root,self.config,self.home,self.launcher)
  self.assertFalse((self.base/'outside').exists())
 def test_shortcut_failure_does_not_activate_release(self):
  first=self.install('0.2.0')
  with self.assertRaises(RuntimeError):install_package(*self.package('0.2.1'),self.root,self.config,self.home,self.launcher,lambda *_:(_ for _ in ()).throw(RuntimeError('shortcut')))
  self.assertEqual(read_install(self.root),first)
 def test_direct_development_exe_ignores_accidental_empty_config(self):
  (self.base/'pyproject.toml').write_text('name="CyAIOrchestrator"');exe=self.base/'dist'/'CyAIOrchestrator';exe.mkdir(parents=True);(exe/'config.json').write_text('{}');self.assertEqual(resolve_config(exe),self.config)
 def test_explicit_missing_config_is_not_recreated(self):
  with self.assertRaises(ValueError):resolve_config(self.root,self.base/'missing.json')
 def test_installed_launch_uses_stable_pointer(self):
  self.install('0.2.0')
  with patch('cyai.launch_config.user_home',return_value=self.home):self.assertEqual(resolve_config(self.root),self.config)
