import re
import unittest
import zipfile
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "cyai" / "web" / "cyannota"


class CyAnnotaBundleTests(unittest.TestCase):
    """CyAnnota 0.3.10 refused every pasted or dropped image in a CyAI session. The shipped copy must not."""

    def test_the_shipped_bundle_lets_cyai_sessions_import_images(self):
        entry = re.search(r'src="\./assets/(index-[\w-]+\.js)"', (WEB / "index.html").read_text(encoding="utf-8")).group(1)
        bundle = (WEB / "assets" / entry).read_text(encoding="utf-8")
        guards = re.findall(r"if\(([^()]{0,80})\)return \w+\(\w+\(`The media linked to `", bundle)
        self.assertTrue(guards, "le garde-fou du média lié a changé de forme : revérifier le collage d’images dans CyAnnota")
        for guard in guards:
            self.assertIn("providerId!==`cyai`", guard, "une session CyAI doit pouvoir coller une image : " + guard)

    def test_the_shipped_source_carries_the_same_change(self):
        with zipfile.ZipFile(WEB / "source.zip") as source:
            page = source.read("app/page.tsx").decode("utf-8")
        model_start=page.index("async function loadModelFiles(")
        self.assertIn("providerId !== 'cyai'",page[model_start:model_start+600])
        start = page.index("async function loadImageFile(")
        self.assertIn("providerId !== 'cyai'", page[start:start + 400])


if __name__ == "__main__":
    unittest.main()
