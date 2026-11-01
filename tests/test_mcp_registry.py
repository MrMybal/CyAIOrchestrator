import unittest
from types import SimpleNamespace
from unittest.mock import patch
import test_core
from cyai.app_mcp import call

class RegistryTests(unittest.TestCase):
    def setUp(self):self.f=test_core.CoreTests();self.f.setUp();self.s=self.f.service
    def tearDown(self):self.f.tearDown()
    def test_agent_registers_and_uses_tools_without_restart(self):
        control=SimpleNamespace(conversation_id=self.f.conversation,planning=False,check=lambda:None,approve=lambda _:True)
        data={'name':'Blender','project_id':self.f.project,'config':{'mcpServers':{'Blender':{'command':'python','args':['server.py'],'cwd':str(self.f.root),'env':{'TEST_MCP':'yes'}}}}}
        with patch.object(self.s.plugins,'rpc',return_value={'tools':[{'name':'scene','inputSchema':{'type':'object'}}]}) as rpc:
            added=call(self.s,'cyai_call',{'action':'mcp_local_register','arguments':data},[self.f.project],control)
            rpc.assert_not_called()
            self.assertEqual(self.s.plugins.plugin(added['id'],self.f.project)['env'],{'TEST_MCP':'yes'})
            result=call(self.s,'cyai_call',{'action':'mcp_local_test','arguments':{'id':added['id'],'project_id':self.f.project}},[self.f.project],control)
            self.assertTrue(result['ok']);self.assertEqual(result['tools'][0]['name'],'scene')
            catalog=call(self.s,'cyai_call',{'action':'plugin_catalog','arguments':{'id':added['id'],'project_id':self.f.project}},[self.f.project],control)
            self.assertEqual(catalog['tools'][0]['name'],'scene')
    def test_registration_does_not_expose_to_every_project(self):
        added=self.s.action('mcp_local_register',{'config':{'mcpServers':{'Hidden':{'command':'python'}}}})
        with self.assertRaisesRegex(ValueError,'désactivé'):self.s.plugins.plugin(added['id'],self.f.project)
    def test_readonly_client_cannot_register(self):
        with self.assertRaises(ValueError):call(self.s,'cyai_call',{'action':'mcp_local_register','arguments':{'config':{'mcpServers':{'x':{'command':'python'}}}}},[self.f.project])
