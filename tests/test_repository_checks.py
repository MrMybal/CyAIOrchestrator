import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import tomllib
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from check_repository import candidate_files, inspect_candidates, scan
ROOT=Path(__file__).resolve().parents[1]


class RepositoryCheckTests(unittest.TestCase):
    def test_local_state_and_binary_dependencies_are_excluded_from_candidates(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            subprocess.run(['git','init',str(root)],check=True,capture_output=True)
            (root/'.gitignore').write_bytes((ROOT/'.gitignore').read_bytes())
            for name in ['source.py','config.json','secret.key','model.gguf','ffmpeg.exe','releases/setup.exe','.data/state.sqlite3','test-results/report.json','build-next/build.pkg','cyai/web/cyannota/ffmpeg/ffmpeg-core.wasm.part0']:
                file=root/name;file.parent.mkdir(parents=True,exist_ok=True);file.write_text('test')
            self.assertEqual(candidate_files(root),['.gitignore','source.py'])

    def test_already_tracked_ignored_file_still_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);subprocess.run(['git','init',str(root)],check=True,capture_output=True)
            (root/'config.json').write_text('{}');subprocess.run(['git','-C',str(root),'add','config.json'],check=True)
            (root/'.gitignore').write_text('config.json')
            self.assertTrue(any('déjà suivi' in reason for _,reason in inspect_candidates(root,candidate_files(root))))

    def test_catalog_exception_is_scoped_to_one_rule(self):
        config=tomllib.loads((ROOT/'.gitleaks.toml').read_text())
        self.assertNotIn('allowlists',config)
        self.assertEqual(config['rules'][0]['id'],'generic-api-key')
        self.assertEqual(config['rules'][0]['allowlists'][0]['condition'],'AND')

    def test_catalog_exception_does_not_hide_another_api_key(self):
        executable=Path(os.environ.get('GITLEAKS_BINARY',str(ROOT/'test-results/security-tools/gitleaks.exe')))
        if not executable.is_file():self.skipTest('Gitleaks executable not provided')
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);file=root/'cyai/piper_catalog.json';file.parent.mkdir()
            file.write_text(json.dumps({'key':'en_US-cmu_arctic_slt-medium','api_key':secrets.token_urlsafe(32)}))
            count=scan(executable,ROOT,root,root/'findings.json')
            self.assertEqual(count,1)
            self.assertEqual(json.loads((root/'findings.json').read_text())[0]['RuleID'],'generic-api-key')

    def test_build_fingerprint_exception_does_not_hide_credentials(self):
        executable=Path(os.environ.get('GITLEAKS_BINARY',str(ROOT/'test-results/security-tools/gitleaks.exe')))
        if not executable.is_file():self.skipTest('Gitleaks executable not provided')
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);file=root/'Documentation/DocData/build-info.json';file.parent.mkdir(parents=True)
            file.write_text(json.dumps({'.CyDocBuild/manual/en/api-integration.md':secrets.token_hex(32),'api_key':secrets.token_urlsafe(32)},indent=2))
            count=scan(executable,ROOT,root,root/'findings.json')
            self.assertEqual(count,1)
            self.assertEqual(json.loads((root/'findings.json').read_text())[0]['RuleID'],'generic-api-key')
