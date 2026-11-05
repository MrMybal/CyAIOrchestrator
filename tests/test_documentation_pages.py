"""Pages publishes the actual reader, with language-correct README links."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from stage_documentation_pages import stage_pages

class PagesTests(unittest.TestCase):
    def test_only_verified_export_is_staged_and_unknown_files_are_refused(self):
        parent=ROOT/'test-results';parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='pages-stage-',dir=parent) as temporary:
            target=Path(temporary)/'site'
            stage_pages(ROOT,target)
            info=json.loads((ROOT/'cyai/help/build-info.json').read_text('utf-8'))
            expected=set(info['outputs'])|{'.nojekyll'}
            self.assertEqual({p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()},expected)
            self.assertFalse((target/'build-info.json').exists())
            for name in info['outputs']:
                self.assertEqual((target/name).read_bytes(),(ROOT/'cyai/help'/name).read_bytes(),name)
            for name in ('index.html','data.js','cyai-reader.js','viewer.css','media-image.js'):
                self.assertTrue((target/name).is_file())
            (target/'local.sqlite3').write_text('disposable test fixture','utf-8')
            with self.assertRaises(ValueError):stage_pages(ROOT,target)
            self.assertTrue((target/'local.sqlite3').is_file())
    def test_readme_links_select_the_right_reader_language(self):
        for name,route in [('README.md','en/start'),('cyai/evaluation_kit/README.md','fr/reference-cyai-evaluation-kit-readme'),('documentation/vendor/README.md','en/reference-docs-user-guide')]:
            self.assertIn('[Documentation](https://mrmybal.github.io/CyAIOrchestrator/#/'+route+')',(ROOT/name).read_text('utf-8'))
        workflow=(ROOT/'.github/workflows/documentation-pages.yml').read_text('utf-8-sig')
        self.assertIn('path: dist-docs-pages',workflow)
        self.assertNotIn('path: .\n',workflow)

if __name__=='__main__':unittest.main()
