import io,json,unittest,zipfile
from pathlib import Path
import test_core
from cyai.media import upload,context_media,stage_originals,locate

class CymdTests(unittest.TestCase):
    def setUp(self):self.f=test_core.CoreTests();self.f.setUp()
    def tearDown(self):self.f.tearDown()
    def attach(self,entries):
        out=io.BytesIO()
        with zipfile.ZipFile(out,'w') as z:
            for name,value in entries:z.writestr(name,value)
        raw=out.getvalue()
        return upload(self.f.service,self.f.conversation,'Aiguille.cymd',io.BytesIO(raw),len(raw))['id']
    def test_markdown_and_images_are_transmitted_and_other_assets_disclosed(self):
        id=self.attach([('manifest.json',json.dumps({'main':'description.md'})),('description.md','# Aiguille\n![vue](assets/vue.png)'),('assets/vue.png',b'PNG'),('assets/model.glb',b'GLB')])
        images,notes=context_media(self.f.store,self.f.conversation,[id])
        self.assertEqual(len(images),1)
        self.assertIn('# Aiguille','\n'.join(notes))
        self.assertIn('assets/vue.png','\n'.join(notes))
        self.assertIn('contenu non transmis','\n'.join(notes))
        self.assertNotIn('Contenu binaire non transmis','\n'.join(notes))
    def test_legacy_markdown_fallback(self):
        id=self.attach([('document.md','Texte français')])
        self.assertIn('Texte français','\n'.join(context_media(self.f.store,self.f.conversation,[id])[1]))
    def test_invalid_container_is_reported_instead_of_silent_omission(self):
        id=self.attach([('assets/file.bin',b'not markdown')])
        self.assertIn('Extraction automatique impossible','\n'.join(context_media(self.f.store,self.f.conversation,[id])[1]))
        originals=stage_originals(self.f.store,self.f.conversation,[id],str(self.f.root))
        self.assertEqual(Path(originals[0]['path']).read_bytes(),locate(self.f.store,id)[2].read_bytes())
