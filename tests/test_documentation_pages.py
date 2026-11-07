"""Pages publishes the actual reader, with language-correct README links."""
import json
from pathlib import Path
import shutil
import sys
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from stage_documentation_pages import OWNER, stage_pages

@unittest.skipUnless(shutil.which('node'),'Node.js is required for the Pages showcase')
class PagesTests(unittest.TestCase):
    def test_only_verified_export_is_staged_and_unknown_files_are_refused(self):
        parent=ROOT/'test-results';parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='pages-stage-',dir=parent) as temporary:
            target=Path(temporary)/'site'
            stage_pages(ROOT,target)
            info=json.loads((ROOT/'Documentation/DocData/build-info.json').read_text('utf-8'))
            showcase=json.loads((ROOT/'dist/website/.cyai-showcase.json').read_text('utf-8'))
            expected=set(info['outputs'])|set(showcase['files'])|{'.nojekyll',OWNER,'DocData/pages-entry.js'}
            self.assertEqual({p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()},expected)
            self.assertFalse((target/'build-info.json').exists())
            self.assertEqual((target/'index.html').read_bytes(),(ROOT/'dist/website/index.html').read_bytes())
            for name in showcase['files']:
                self.assertEqual((target/name).read_bytes(),(ROOT/'dist/website'/name).read_bytes(),name)
            stage_pages(ROOT,target)  # An intact owned artifact can be regenerated.
            for name in info['outputs']:
                self.assertEqual((target/name).read_bytes(),(ROOT/'Documentation'/name).read_bytes(),name)
            for name in ('Documentation.html','DocData/data.js','DocData/viewer.js','DocData/viewer.css','DocData/media-image.js'):
                self.assertTrue((target/name).is_file())
            (target/'local.sqlite3').write_text('disposable test fixture','utf-8')
            with self.assertRaises(ValueError):stage_pages(ROOT,target)
            self.assertTrue((target/'local.sqlite3').is_file())
    def test_modified_pages_are_preserved(self):
        parent=ROOT/'test-results';parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='pages-modified-',dir=parent) as temporary:
            target=Path(temporary)/'site';stage_pages(ROOT,target)
            file=target/'Documentation.html';file.write_text('edited reader fixture','utf-8')
            with self.assertRaisesRegex(ValueError,'Modified generated resource'):
                stage_pages(ROOT,target)
            self.assertEqual(file.read_text('utf-8'),'edited reader fixture')

    def test_legacy_root_routes_open_the_complete_portable_reader(self):
        # Execute the shipped classic script without a DOM: a legacy link must
        # redirect before initializing any showcase controls.
        script="""const {readFileSync}=require('node:fs');const vm=require('node:vm');
let destination;const location={hash:process.argv[2],search:'?ref=shared&lang=fr',replace:url=>destination=url};
vm.runInNewContext(readFileSync(process.argv[1],'utf8'),{location});
process.stdout.write(JSON.stringify(destination));"""
        for route in ['#/en/start','#/fr/orchestration','#/fr/background/tasks']:
            result=subprocess.run([shutil.which('node'),'-e',script,str(ROOT/'website/source/site.js'),route],capture_output=True,text=True,check=True)
            self.assertEqual(json.loads(result.stdout),'./manual/Documentation.html?ref=shared&lang=fr'+route)

    def test_readme_links_select_the_right_reader_language(self):
        for name,route in [('README.md','en/start'),('cyai/evaluation_kit/README.md','fr/background')]:
            self.assertIn('[Documentation](https://mrmybal.github.io/CyAIOrchestrator/#/'+route+')',(ROOT/name).read_text('utf-8'))
        for name,locale,label in [('README.md','en','Showcase'),('README.fr.md','fr','Présentation')]:
            readme=(ROOT/name).read_text('utf-8')
            self.assertIn(f'<a href="https://mrmybal.github.io/CyAIOrchestrator/?lang={locale}">{label}</a>',readme)
            self.assertIn(f'Documentation.html#/{locale}/start',readme)
        workflow=(ROOT/'.github/workflows/documentation-pages.yml').read_text('utf-8-sig')
        self.assertIn('path: dist-docs-pages',workflow)
        self.assertNotIn('path: .\n',workflow)

if __name__=='__main__':unittest.main()
