import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from cyai.plugins import Plugins


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.service=Mock(config={},config_path=Path(self.tmp.name)/'config.json')
        self.plugins=Plugins(self.service)
        self.p=self.plugins.config['plugins']['cyprojectcodex']
        self.p['enabled']=True
        self.p['projects']={'local':{'external_project_id':'external','enabled':True}}
    def tearDown(self):self.tmp.cleanup()
    def test_project_scope_overrides_agent_argument_and_filters_project_names(self):
        self.plugins.rpc=Mock(return_value={'content':[{'type':'text','text':json.dumps({'projects':[{'id':'external'},{'id':'other'}]})}]})
        r=self.plugins.read('cyprojectcodex','local','get_project',{'projectId':'other'})
        self.assertEqual(self.plugins.rpc.call_args.args[2]['arguments']['projectId'],'external')
        self.assertEqual(len(json.loads(r['content'][0]['text'])['projects']),1)
    def test_write_tool_and_unbound_project_denied(self):
        for tool,project in [('create_element','local'),('get_project','unbound'),('list_projects','local')]:
            with self.assertRaises(ValueError):self.plugins.read('cyprojectcodex',project,tool,{})
    def test_gateway_requires_valid_grant(self):
        with self.assertRaises(ValueError):self.plugins.gateway('invalid',{'method':'tools/list'})
        self.plugins.grants['valid']='local'
        self.assertEqual({t['name'] for t in self.plugins.gateway('valid',{'method':'tools/list'})['tools']},{'list_plugins','read_plugin','cyai_actions','cyai_call'})
    def test_manifest_rejects_remote_token_destination(self):
        with self.assertRaises(ValueError):self.plugins.save({'manifest':{'id':'remote','name':'Remote','type':'mcp','transport':'http','url':'https://example.com','read_tools':[]}})
