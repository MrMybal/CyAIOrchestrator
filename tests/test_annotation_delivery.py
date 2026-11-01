import io,json,unittest,zipfile,base64
import test_core
from cyai.media import upload,context_media
from cyai.annotation_delivery import receive
class AnnotationDeliveryTests(unittest.TestCase):
 def setUp(self):self.f=test_core.CoreTests();self.f.setUp();self.f.service.plugins.config if False else None
 def tearDown(self):self.f.tearDown()
 def archive(self,files):
  b=io.BytesIO()
  with zipfile.ZipFile(b,'w') as z:
   for name,data in files.items():z.writestr(name,data)
  raw=b.getvalue();return upload(self.f.service,self.f.conversation,'test.cyannota.zip',io.BytesIO(raw),len(raw))['id']
 def test_delivery_contains_text_and_real_images(self):
  id=self.archive({'tabs/1/prompt.md':'Correction : déplacer le bouton','tabs/1/images/annotated.png':b'image bytes','workspace.cyannota.json':'{}'})
  r=receive(self.f.service,{'conversation_id':self.f.conversation,'id':id});images,notes=context_media(self.f.store,self.f.conversation,r['ids']);self.assertEqual(len(images),1);self.assertEqual(base64.b64decode(images[0]['data']),b'image bytes');self.assertIn('déplacer','\n'.join(notes))
 def test_reject_bad_archive_without_partial_files(self):
  id=self.archive({'../escape.png':b'bad','prompt.md':'text'})
  with self.assertRaises(ValueError):receive(self.f.service,{'conversation_id':self.f.conversation,'id':id})
  self.assertEqual(len(self.f.store.rows('SELECT id FROM files')),1)

 def test_model_export_preserves_original_bytes(self):
  id=self.archive({'tabs/ship/prompt.md':'Corriger la coque','tabs/ship/model.glb':b'glTF-original','tabs/ship/views/01.png':b'view'})
  r=receive(self.f.service,{'conversation_id':self.f.conversation,'id':id})
  self.assertEqual(r['models'],1);self.assertEqual(r['images'],1)
  from cyai.media import locate
  model=next(locate(self.f.store,i) for i in r['ids'] if locate(self.f.store,i)[0]['name']=='model.glb')
  self.assertEqual(model[2].read_bytes(),b'glTF-original')
