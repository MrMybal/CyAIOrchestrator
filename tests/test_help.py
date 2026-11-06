"""CyDoc content, routes, distribution and removal of the HTTP reader."""
import json
from html.parser import HTMLParser
from pathlib import Path
import re
import sys
import threading
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen
from cyai.documentation import canonical_route, documentation_url, DocumentationActions, DocumentationWindows
from cyai.server import make_server
ROOT = Path(__file__).resolve().parents[1]
HELP = ROOT/'Documentation'
DATA = HELP/'DocData'
sys.path.insert(0,str(ROOT/'scripts'))
from build_documentation import verify_export, digest

class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[];self.images=[];self.ids=set()
    def handle_starttag(self,tag,attrs):
        values=dict(attrs)
        if tag=='a' and values.get('href'):self.links.append(values['href'])
        if tag=='img':self.images.append(values.get('src',''))
        if values.get('id'):self.ids.add(values['id'])

class DocumentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest=json.loads((DATA/'manifest.json').read_text('utf-8'))
        cls.pages={(p['locale'],p['id']):p for p in cls.manifest['pages']}
    def test_guides_remain_bilingual_with_common_anchors(self):
        en={p.stem for p in (ROOT/'.CyDocBuild/manual/en').glob('*.md')}
        fr={p.stem for p in (ROOT/'.CyDocBuild/manual/fr').glob('*.md')}
        self.assertEqual(len(en),28);self.assertEqual(en,fr)
        for id in en:
            a,b=self.pages['en',id],self.pages['fr',id]
            self.assertEqual([h['id'] for h in a['headings']],[h['id'] for h in b['headings']],id)
            self.assertTrue(a['revision']);self.assertEqual(a['revision'],b['sourceRevision'])
        report=json.loads((DATA/'translation-report.json').read_text('utf-8'))
        self.assertFalse(report['missing']);self.assertFalse(report['outdated'])
        self.assertFalse(en & {p['id'] for p in report['untracked']})
        self.assertEqual({p['id'] for p in report['untracked']},{'api-cyai-documentation-documentation-url-url','api-cyai-documentation-canonical-route-route'})
        self.assertEqual(self.manifest['defaultLocale'],'en')
    def test_all_local_document_links_and_assets(self):
        parsers={}
        for key,page in self.pages.items():
            parser=Links();parser.feed(page['html']);parsers[key]=parser
            for asset in page['assets']:
                target=(DATA/asset).resolve();self.assertTrue(target.is_relative_to(DATA.resolve()))
                self.assertTrue(target.is_file(),asset)
            for src in parser.images:self.assertTrue(src.startswith('assets/'),src)
        for key,parser in parsers.items():
            for link in parser.links:
                if not link.startswith('#/'):continue
                segments=urlsplit(link[1:]).path.strip('/').split('/')
                locale,id=map(unquote,segments[:2]);id=self.manifest.get('aliases',{}).get(id,id)
                self.assertIn((locale,id),self.pages,(key,link))
                if len(segments)>2:self.assertIn(unquote(segments[2]),parsers[locale,id].ids,(key,link))
    def test_human_content_excludes_internal_records_and_implementations(self):
        self.assertEqual({p.name for p in HELP.iterdir()},{'Documentation.html','DocAI.md','DocData'})
        self.assertTrue((ROOT/'.CyDocBuild/internal/previous-migration-inventory.json').is_file())
        ids={page['id'] for page in self.manifest['pages']}
        self.assertFalse({'migration-inventory','translation-report','reference-validation'} & ids)
        self.assertFalse(any(p['kind']=='source' or p['id'].startswith('source-') for p in self.manifest['pages']))
        for page in self.manifest['pages']:
            self.assertNotIn('translation is pending',page['text'])
            self.assertNotIn('reste à compléter',page['text'])
            self.assertNotIn('SourceFile',page['html'])
            if page['locale']=='fr':
                original=self.pages['en',page['id']]
                self.assertNotEqual(original['text'],page['text'],page['id'])
                self.assertEqual([h['id'] for h in original['headings']],[h['id'] for h in page['headings']])
        self.assertFalse(any(p.suffix in {'.py','.ts','.tgz'} for p in HELP.rglob('*')))
        for locale in ('en','fr'):
            api=self.pages[locale,'api-integration']
            self.assertTrue({'parameters','native','help-links'} <= {h['id'] for h in api['headings']})
        self.assertTrue((HELP/'DocAI.md').read_text('utf-8').startswith('# Documentation integration notes'))
        self.assertNotIn('Documentation integration notes for coding assistants',str(self.manifest['pages']))

    def test_navigation_tree_and_public_signatures(self):
        import ast
        from cyai import documentation
        import inspect
        self.assertGreater(sum(bool(p.get('parent')) for p in self.manifest['pages']),30)
        for page in self.manifest['pages']:
            if page.get('parent'):self.assertIn((page['locale'],page['parent']),self.pages)
        functions={node.name:node for node in ast.parse(inspect.getsource(documentation)).body if isinstance(node,ast.FunctionDef)}
        for locale in ('en','fr'):
            symbols=json.loads((ROOT/'.CyDocBuild/api'/f'{locale}.json').read_text('utf-8'))['symbols']
            for symbol in symbols:
                name=symbol['name'].rsplit('.',1)[-1]
                node=functions[name]
                self.assertEqual([a.arg for a in node.args.args],[p['name'] for p in symbol['parameters']])
                self.assertEqual(name+str(inspect.signature(getattr(documentation,name))),symbol['signature'])
                self.assertTrue(all(p['description'] for p in symbol['parameters']))
                self.assertTrue(symbol['returns'])
        self.assertEqual(canonical_route('api-help-links','fr','parameters')['pageId'],'api-integration')

    def test_source_checksums_survive_cross_platform_checkouts(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ('.gitignore','page.md','data.json'):
                file=Path(folder)/name
                file.write_bytes(b'first\r\nsecond\r\n');windows=digest(file)
                file.write_bytes(b'first\nsecond\n');self.assertEqual(windows,digest(file),name)
                file.write_bytes(b'first\nchanged\n');self.assertNotEqual(windows,digest(file),name)
            file=Path(folder)/'asset.tgz';file.write_bytes(b'\x00\r\n');binary=digest(file)
            file.write_bytes(b'\x00\n');self.assertNotEqual(binary,digest(file))
    def test_file_export_is_fresh_and_only_uses_image_module(self):
        info=verify_export(ROOT)
        self.assertEqual(info['modules'],['image'])
        self.assertEqual({p.name for p in DATA.glob('media-*.js')},{'media-image.js'})
        self.assertFalse((ROOT/'.CyDocBuild/node_modules/three').exists())
        html=(HELP/'Documentation.html').read_text('utf-8')
        self.assertIn("connect-src 'none'",html)
        self.assertNotRegex(html,r'(?:src|href)="https?://')
        self.assertTrue((DATA/'CyDoc-LICENSE.txt').is_file())
        self.assertTrue((DATA/'CyAI-LICENSE.txt').is_file())
        package=(ROOT/'pyproject.toml').read_text('utf-8')
        self.assertIn('"Documentation/DocData/assets/images"',package)
        self.assertNotIn('"help/*"',package)
        self.assertFalse((ROOT/'cyai/help').exists())
        self.assertFalse((ROOT/'cyai/web/help').exists())
        self.assertFalse((ROOT/'cyai/web/help.css').exists())
    def test_routes_fallback_legacy_anchors_media_and_encoding(self):
        route=canonical_route('overview','xx')
        self.assertEqual((route['pageId'],route['locale']),('start','en'))
        self.assertEqual(canonical_route('missing','fr')['pageId'],'start')
        url=documentation_url('start','fr','help-part-1',{'media':'conversation','zoom':1.5},'dark')
        split=urlsplit(url)
        self.assertEqual(split.scheme,'file');self.assertEqual(split.query,'')
        self.assertTrue(split.path.endswith('/Documentation.html'));self.assertTrue(Path(unquote(split.path.lstrip('/') if sys.platform=='win32' else split.path)).is_file())
        self.assertEqual(split.fragment,'/fr/start/help-part-1?media=conversation&theme=midnight&zoom=1.5')
        for kwargs in ({'anchor':'missing'},{'state':{'media':'missing'}}):
            with self.assertRaises(ValueError):canonical_route(**kwargs)
    def test_native_window_reuse_and_settings_contract(self):
        class Signal(list):
            def __iadd__(self,callback):
                self.append(callback);return self
        events=SimpleNamespace(closed=Signal())
        window=Mock(events=events)
        module=SimpleNamespace(create_window=Mock(return_value=window))
        with patch.dict(sys.modules,{'webview':module}):
            manager=DocumentationWindows();result=manager.open('start','fr')
            self.assertTrue(result['url'].startswith('file:'))
            manager.open('context','en')
            module.create_window.assert_called_once();window.evaluate_js.assert_called_once()
            self.assertIn('CYAI_HELP.navigate',window.evaluate_js.call_args.args[0])
            window.show.assert_called_once()
            events.closed[0]();self.assertIsNone(manager.window)
        callback=Mock();actions=DocumentationActions(callback)
        self.assertEqual(actions.open_settings('appearance'),{'opened':True})
        callback.assert_called_once_with('appearance')
        self.assertFalse(hasattr(actions,'callback'))
        with self.assertRaises(ValueError):actions.open_settings('../outside')
        self.assertEqual(DocumentationActions().open_settings('models'),{'opened':False})

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
    def test_only_help_adapter_remains_in_application_server(self):
        with urlopen(self.url+'/help.js') as response:
            self.assertEqual(response.status,200);self.assertIn(b'open_documentation',response.read())
        for path in ('/help/en.json','/help/index.html','/help.css','/help/%2e%2e/server.py'):
            with self.subTest(path=path),self.assertRaises(HTTPError) as error:urlopen(self.url+path)
            self.assertEqual(error.exception.code,404)
    def test_existing_api_still_requires_authentication(self):
        with self.assertRaises(HTTPError) as error:urlopen(self.url+'/api/state')
        self.assertEqual(error.exception.code,403)

if __name__=='__main__':unittest.main()
