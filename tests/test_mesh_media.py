import unittest,tempfile,json,threading,urllib.request,http.cookiejar
from pathlib import Path
from unittest.mock import patch
import test_core
from cyai.media import preview,local_path,open_local
from cyai.server import make_server
class MeshMediaTests(unittest.TestCase):
 def setUp(self):self.f=test_core.CoreTests();self.f.setUp()
 def tearDown(self):self.f.tearDown()
 def test_external_mesh_preview_and_windows(self):
  with tempfile.TemporaryDirectory() as folder:
   path=Path(folder)/'generated.glb';path.write_bytes(b'glTF-test')
   data={'conversation_id':self.f.conversation,'path':str(path)}
   result=preview(self.f.service,data)
   self.assertEqual(result['name'],'generated.glb')
   with patch('cyai.media.os.startfile') as start:
    open_local(self.f.service,data);start.assert_called_once_with(str(path.resolve()))
   protected=Path(folder)/'secrets.json';protected.write_text('{}')
   with self.assertRaises(ValueError):local_path(self.f.service,self.f.conversation,str(protected))
 def test_modules_served(self):
  server,_=make_server(self.f.service,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
  base='http://127.0.0.1:'+str(server.server_port)
  try:
   for asset in ('mesh-viewer.js','three/three.module.js','three/three.core.js','three/GLTFLoader.js','three/BufferGeometryUtils.js','three/OrbitControls.js'):
    with urllib.request.urlopen(base+'/'+asset) as response:
     self.assertEqual(response.status,200);self.assertIn('javascript',response.headers['Content-Type'])
  finally:server.shutdown();server.server_close()
