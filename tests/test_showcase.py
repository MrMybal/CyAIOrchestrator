"""Standalone consumer, artifact boundaries and cache renewal for the showcase."""
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

@unittest.skipUnless(shutil.which('node'),'Node.js is needed for showcase consumer tests')
class ShowcaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parent=ROOT/'test-results';parent.mkdir(exist_ok=True)
        cls.temporary=tempfile.TemporaryDirectory(prefix='showcase-consumer-',dir=parent)
        cls.project=Path(cls.temporary.name)/'app';cls.project.mkdir()
        info=json.loads((ROOT/'Documentation/DocData/build-info.json').read_text('utf-8'))
        catalog=json.loads((ROOT/'website/source/screens.json').read_text('utf-8'))
        names=set(info['inputs'])|{'pyproject.toml','LICENSE','cyai/web/cyai-logo.png','.CyDocBuild/host/index.html','.CyDocBuild/host/pages-entry.js'}
        names|={'Documentation/'+name for name in info['outputs']}|{'Documentation/DocData/build-info.json'}
        names|={name for item in catalog.values() for name in item['files'].values()}
        names|={p.relative_to(ROOT).as_posix() for p in (ROOT/'website').rglob('*') if p.is_file()}
        for name in names:
            source=ROOT/name;target=cls.project/name
            if not source.resolve().is_relative_to(ROOT.resolve()):raise ValueError('Unexpected consumer source')
            target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def build(self,name,success=True):
        output=self.project/'test-results'/name/'site'
        result=subprocess.run([shutil.which('node'),'website/build.mjs','--output='+str(output)],cwd=self.project,capture_output=True,text=True,encoding='utf-8')
        if success:self.assertEqual(result.returncode,0,result.stderr)
        else:self.assertNotEqual(result.returncode,0)
        return output,result

    def test_portable_consumer_without_git_preserves_complete_manual(self):
        self.assertFalse((self.project/'.git').exists())
        output,_=self.build('portable')
        info=json.loads((self.project/'Documentation/DocData/build-info.json').read_text('utf-8'))
        for name in [*info['outputs'],'DocData/build-info.json']:
            self.assertEqual((output/'manual'/name).read_bytes(),(self.project/'Documentation'/name).read_bytes(),name)
        self.assertTrue((output/'manual/index.html').is_file())
        self.assertTrue((output/'manual/DocData/pages-entry.js').is_file())
        metadata=json.loads((output/'.cyai-showcase.json').read_text('utf-8'))
        self.assertEqual(metadata['locales'],['en','fr'])
        self.assertEqual(set(metadata['files'])|{'.cyai-showcase.json'},{p.relative_to(output).as_posix() for p in output.rglob('*') if p.is_file()})
        self.assertFalse(any(name.endswith(('.sqlite3','.dpapi','.gguf')) or name.startswith(('source/','.git/','.CyDocBuild/')) for name in metadata['files']))
        html=(output/'index.html').read_text('utf-8')
        self.assertIn('<html lang="en">',html)
        self.assertIn('Alpha',html)
        self.assertIn('./manual/Documentation.html#/en/start',html)
        self.assertNotIn('type="module"',html)
        for url in re.findall(r'(?:href|src)="([^"]+)"',html):
            if url.startswith('./'):self.assertTrue((output/url.split('#')[0].split('?')[0]).is_file(),url)
        script=re.search(r'<script defer src="([^"]+)"',html).group(1)
        self.assertNotRegex((output/script).read_text('utf-8'),r'\bfetch\s*\(')

    def test_unknown_output_is_preserved_and_not_published(self):
        output,_=self.build('unknown')
        private=output/'personal.sqlite3';private.write_text('disposable fixture','utf-8')
        _,result=self.build('unknown',False)
        self.assertIn('Unexpected files',result.stderr)
        self.assertEqual(private.read_text('utf-8'),'disposable fixture')

    def test_css_and_script_changes_renew_references(self):
        output,_=self.build('cache')
        first=(output/'index.html').read_text('utf-8')
        originals={name:(self.project/'website/source'/name).read_bytes() for name in ['styles.css','site.js']}
        try:
            for name,data in originals.items():(self.project/'website/source'/name).write_bytes(data+b'\n/* consumer cache revision */\n')
            self.build('cache')
            second=(output/'index.html').read_text('utf-8')
            for extension in ['css','js']:
                pattern=r'\./assets/site\.[a-f0-9]{12}\.'+extension
                before=re.search(pattern,first).group();after=re.search(pattern,second).group()
                self.assertNotEqual(before,after)
                self.assertTrue((output/after).is_file())
                self.assertFalse((output/before).exists())
        finally:
            for name,data in originals.items():(self.project/'website/source'/name).write_bytes(data)

    def test_missing_translation_cannot_replace_previous_export(self):
        output,_=self.build('translation');before=(output/'index.html').read_bytes()
        file=self.project/'website/source/fr.json';original=file.read_bytes()
        try:
            messages=json.loads(original);del messages['viewer.close'];file.write_text(json.dumps(messages),'utf-8')
            _,result=self.build('translation',False)
            self.assertIn('translation keys differ',result.stderr)
            self.assertEqual((output/'index.html').read_bytes(),before)
        finally:file.write_bytes(original)

    def test_catalog_cannot_include_a_file_outside_project(self):
        output,_=self.build('escape');before=(output/'index.html').read_bytes()
        file=self.project/'website/source/screens.json';original=file.read_bytes()
        outside=self.project.parent/'outside.png';outside.write_bytes(b'outside consumer fixture')
        try:
            catalog=json.loads(original);catalog['conversation']['files']['en']='../outside.png';file.write_text(json.dumps(catalog),'utf-8')
            _,result=self.build('escape',False)
            self.assertIn('Source outside project',result.stderr)
            self.assertEqual((output/'index.html').read_bytes(),before)
        finally:file.write_bytes(original)

if __name__=='__main__':unittest.main()
