import io,json,unittest,threading,http.cookiejar,urllib.request
import test_core
from cyai.media import upload,locate,context_media
from cyai.server import make_server
class MediaTests(unittest.TestCase):
 def setUp(self):self.f=test_core.CoreTests();self.f.setUp()
 def tearDown(self):self.f.tearDown()
 def test_upload_context_and_message_binding(self):
  f=self.f;r=upload(f.service,f.conversation,'../note.txt',io.BytesIO(b'hello attachment'),16)
  self.assertEqual(r['name'],'note.txt');images,notes=context_media(f.store,f.conversation,[r['id']]);self.assertIn('hello attachment',notes[0])
  m=f.run_job(f.spec(context={'file_ids':[r['id']]}));self.assertEqual(m['status'],'succeeded')
  row,meta,path=locate(f.store,r['id']);self.assertEqual(len(meta['message_ids']),1)
  other=f.action_conversation('chat')
  with self.assertRaises(ValueError):context_media(f.store,other,[r['id']])
 def test_binary_explicit_and_interrupted_upload(self):
  f=self.f;r=upload(f.service,f.conversation,'clip.mp4',io.BytesIO(b'\0abc'),4)
  _,notes=context_media(f.store,f.conversation,[r['id']]);self.assertIn('fichier original',notes[0])
  with self.assertRaises(ValueError):upload(f.service,f.conversation,'truncated.txt',io.BytesIO(b'a'),3)
  self.assertEqual(len(list((f.store.path.parent/'attachments').iterdir())),1)
 def test_media_auth_and_range(self):
  f=self.f;r=upload(f.service,f.conversation,'clip.mp4',io.BytesIO(b'0123456789'),10)
  server,_=make_server(f.service,0);t=threading.Thread(target=server.serve_forever,daemon=True);t.start();base='http://127.0.0.1:'+str(server.server_port)
  try:
   with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(base+'/media/'+r['id'])
   o=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()));o.open(base+'/').read()
   with o.open(urllib.request.Request(base+'/media/'+r['id'],headers={'Range':'bytes=2-5'})) as response:self.assertEqual(response.status,206);self.assertEqual(response.read(),b'2345')
   with o.open(urllib.request.Request(base+'/media/'+r['id'],headers={'Range':'bytes=-3'})) as response:self.assertEqual(response.read(),b'789')
   request=urllib.request.Request(base+'/api/upload?conversation_id='+f.conversation+'&name=hello.txt',data=b'hello',headers={'X-CyAI':'1','Content-Type':'application/octet-stream'})
   uploaded=json.load(o.open(request));self.assertEqual(locate(f.store,uploaded['id'])[2].read_bytes(),b'hello')
   f.service.action('delete_file',{'conversation_id':f.conversation,'id':uploaded['id']});self.assertFalse((f.store.path.parent/'attachments'/uploaded['id']).exists())

  finally:server.shutdown();server.server_close()
