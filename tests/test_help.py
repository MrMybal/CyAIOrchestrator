"""The guide is bundled, bilingual and served only from its own static directory."""
import json
from pathlib import Path
import threading
import unittest
from types import SimpleNamespace
from urllib.error import HTTPError
from urllib.request import urlopen
from cyai.server import make_server
ROOT = Path(__file__).resolve().parents[1]
HELP = ROOT / 'cyai/web/help'

class DocumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs={lang:json.loads((HELP/(lang+'.json')).read_text('utf-8')) for lang in ('en','fr')}

    def test_complete_matching_chapters_and_labels(self):
        en,fr=self.docs['en'],self.docs['fr']
        self.assertEqual(len(en['chapters']),27)
        self.assertEqual(set(en['labels']),set(fr['labels']))
        self.assertEqual(set(en['groups']),set(fr['groups']))
        self.assertEqual([c['id'] for c in en['chapters']],[c['id'] for c in fr['chapters']])
        self.assertEqual(len({c['id'] for c in en['chapters']}),27)
        for a,b in zip(en['chapters'],fr['chapters']):
            self.assertEqual(a['group'],b['group'])
            self.assertEqual([v['type'] for v in a['blocks']],[v['type'] for v in b['blocks']])
            self.assertTrue(a['summary'] and b['summary'])
            self.assertGreaterEqual(len(a['blocks']),3)

    def test_links_tables_diagrams_and_localized_images(self):
        for lang,doc in self.docs.items():
            ids={c['id'] for c in doc['chapters']};images=set();diagrams=[]
            self.assertEqual(doc['language'],lang)
            for chapter in doc['chapters']:
                self.assertIn(chapter['group'],doc['groups'])
                for block in chapter['blocks']:
                    if block['type']=='related': self.assertLessEqual(set(block['topics']),ids)
                    if block['type']=='table':
                        for row in block['rows']:self.assertEqual(len(row),len(block['headers']))
                    if block['type']=='image':
                        file=HELP/'images'/block['file'];self.assertTrue(file.is_file(),file)
                        self.assertTrue(block['file'].endswith('-'+lang+'.png'))
                        self.assertTrue(file.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'))
                        self.assertTrue(block['alt'] and block['caption']);images.add(block['file'])
                    if block['type']=='diagram':
                        self.assertEqual(len(block['labels']),6 if block['layout']=='parallel' else 5)
                        self.assertTrue(block['title'] and block['caption']);diagrams.append(block)
            self.assertEqual(len(images),3)
            self.assertEqual(len(diagrams),3)

    def test_language_content_is_not_a_placeholder(self):
        for lang,doc in self.docs.items():
            body=' '.join(json.dumps(c,ensure_ascii=False) for c in doc['chapters'])
            self.assertGreater(len(body),35000)
            self.assertNotIn('TODO',body)
        self.assertNotEqual(self.docs['en']['chapters'][0]['summary'],self.docs['fr']['chapters'][0]['summary'])

    def test_package_and_browser_include_resources(self):
        package=(ROOT/'pyproject.toml').read_text('utf-8')
        for pattern in ('web/help/*.json','web/help/images/*.png'):self.assertIn(pattern,package)
        spec=(ROOT/'packaging/CyAIOrchestrator.spec').read_text('utf-8')
        self.assertIn("collect_data_files('cyai')",spec)
        html=(ROOT/'cyai/web/index.html').read_text('utf-8')
        self.assertIn('/help.js',html);self.assertIn('/help.css',html)

class DocumentationHttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        service=SimpleNamespace(config={},engine=SimpleNamespace(secrets=SimpleNamespace(redact=lambda value:value)))
        cls.server,_=make_server(service,0)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url='http://127.0.0.1:'+str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(5)
    def test_offline_content_and_scripts(self):
        for path,mime in [('/help/en.json','application/json'),('/help/fr.json','application/json'),('/help/images/conversation-en.png','image/png'),('/help.js','text/javascript'),('/help.css','text/css')]:
            with urlopen(self.url+path) as response:
                self.assertEqual(response.status,200)
                self.assertIn(mime,response.headers['Content-Type'])
                self.assertIn("default-src 'self'",response.headers['Content-Security-Policy'])
                self.assertGreater(len(response.read()),100)
    def test_traversal_and_unsupported_assets_are_rejected(self):
        for path in ('/help/de.json','/help/%2e%2e/server.py','/help/images/%2e%2e/%2e%2e/cyai-logo.png','/help/images/../../../../config.json','/help/en.json/extra','/help/index.html'):
            with self.subTest(path=path),self.assertRaises(HTTPError) as error:urlopen(self.url+path)
            self.assertEqual(error.exception.code,404)
    def test_existing_api_still_requires_authentication(self):
        with self.assertRaises(HTTPError) as error:urlopen(self.url+'/api/state')
        self.assertEqual(error.exception.code,403)

if __name__=='__main__':unittest.main()
