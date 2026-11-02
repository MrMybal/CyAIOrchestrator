import json
import tempfile
import unittest
from pathlib import Path
from cyai.cytool_discovery import discover

class DiscoveryTests(unittest.TestCase):
    def test_desktop_and_app_folder_preserve_mcp_arguments(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve(); app=root/'app';app.mkdir()
            manifest={'schemaVersion':1,'protocolVersion':'1.0','id':'test','name':'Test','interfaces':['MCP']}
            (app/'CyTool.json').write_text(json.dumps(manifest))
            command=root/'python.exe';command.write_bytes(b'not executed')
            args=['tool.py','--data-dir','data/mcp','mcp']
            (app/'mcp.json').write_text(json.dumps({'mcpServers':{'Test':{'command':str(command),'args':args}}}))
            for folder in (root,app):
                result=discover(str(folder))
                self.assertEqual(result['command'],str(command))
                self.assertEqual(result['args'],args)
                self.assertEqual(result['cwd'],str(root))
                self.assertEqual(result['warnings'],[])
    def test_missing_runtime_and_ambiguous_configs_are_explained(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            (root/'CyTool.json').write_text(json.dumps({'schemaVersion':1,'protocolVersion':'1.0','id':'test','interfaces':['MCP']}))
            (root/'mcp.json').write_text(json.dumps({'mcpServers':{'a':{},'b':{}}}))
            self.assertTrue(discover(tmp)['warnings'])
            self.assertEqual(discover(tmp)['command'],'')
    def test_does_not_search_backups_and_reports_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();(root/'runtime').mkdir()
            (root/'runtime'/'CyTool.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'introuvable'):discover(tmp)
            (root/'CyTool.json').write_text(json.dumps({'schemaVersion':1,'protocolVersion':'1.0','id':'test','interfaces':['MCP']}))
            (root/'tool.py').write_text('raise RuntimeError("must not execute")')
            (root/'mcp.json').write_text('invalid')
            result=discover(tmp)
            self.assertIn('invalide',result['warnings'][0])
            self.assertEqual(result['args'],[str(root/'tool.py'),'--data-dir',str(root/'data/jobs-cyai'),'mcp'])
