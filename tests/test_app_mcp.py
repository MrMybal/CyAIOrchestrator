import json
import shutil
import threading
import time
import unittest
from unittest.mock import Mock
import test_core
from cyai import app_mcp
from cyai.connectors import Control, JsonProcess
from cyai.server import make_server


class AppMcpTests(unittest.TestCase):
    def setUp(self):
        self.fixture=test_core.CoreTests();self.fixture.setUp()
        self.s=self.fixture.service;self.p=self.fixture.project;self.c=self.fixture.conversation
        self.approvals=[]
        self.control=Control(30,lambda d:self.approvals.append(d) or True,lambda *_:None)
        self.control.conversation_id=self.c
    def tearDown(self):self.fixture.tearDown()
    def call(self,name,args=None,control=True,projects=None):
        return app_mcp.call(self.s,'cyai_call',{'action':name,'arguments':args or {}},projects or [self.p],self.control if control else None)
    def test_registry_schemas_and_domain_discovery(self):
        for op in app_mcp.ACTIONS.values():app_mcp.Draft202012Validator.check_schema(op['inputSchema'])
        result=app_mcp.call(self.s,'cyai_actions',{'domain':'local_models'},[self.p])
        self.assertIn('local_model_install',{a['name'] for a in result['actions']})
        self.assertIn('approval_settings',result['user_only'])
    def test_memory_write_approval_and_typed_validation(self):
        result=self.call('save_memory',{'project_id':self.p,'content':'A decision','category':'Architecture','validated':True})
        self.assertEqual(self.s.memory(self.p)[0]['id'],result['id']);self.assertEqual(len(self.approvals),1)
        with self.assertRaises(ValueError):self.call('save_memory',{'project_id':self.p,'content':'X','validated':'yes'})
        self.assertEqual(len(self.approvals),1)
    def test_scope_is_checked_before_approval(self):
        other=self.s.action('create_project',{'name':'Other','root':str(self.fixture.root)})['id']
        c=self.s.action('create_conversation',{'project_id':other})['id']
        for name,args in [('get_conversation',{'conversation_id':c}),('rename_conversation',{'id':c,'title':'Wrong'}),('get_memory',{'project_id':other})]:
            with self.assertRaises(ValueError):self.call(name,args)
        self.assertFalse(self.approvals)
        self.assertEqual(len(self.call('get_state')['projects']),1)
        with self.assertRaises(ValueError):app_mcp.resource_read(self.s,[self.p],'cyai://project/'+other+'/overview')
    def test_refusal_readonly_planning_and_no_self_authorization(self):
        args={'project_id':self.p,'content':'X'}
        with self.assertRaises(ValueError):self.call('save_memory',args,control=False)
        self.control.approve=lambda _:False
        with self.assertRaises(ValueError):self.call('save_memory',args)
        self.control.planning=True
        with self.assertRaises(ValueError):self.call('save_memory',args)
        self.control.planning=False
        with self.assertRaises(ValueError):self.call('agent_settings',{'scope':'conversation','id':self.c,'settings':{'approval_mode':'auto'}})
        with self.assertRaises(ValueError):self.call('approval_settings',{'mode':'auto'})
        self.assertFalse(self.s.memory(self.p))
    def test_download_calls_the_manager_and_returns_job(self):
        self.s.local_models=Mock()
        self.s.local_models.action.return_value={'job_id':'download','status':'running'}
        result=self.call('local_model_install',{'repo':'Qwen/model','filename':'model.gguf'})
        self.assertEqual(result['job_id'],'download')
        self.s.local_models.action.assert_called_once_with('local_model_install',{'repo':'Qwen/model','filename':'model.gguf'})
    def test_settings_do_not_remove_existing_approval_policy(self):
        self.s.action('approval_settings',{'conversation_id':self.c,'mode':'manual'})
        self.call('agent_settings',{'scope':'conversation','id':self.c,'settings':{'instructions':'Hello'}})
        self.assertEqual(json.loads(self.s.conversation(self.c)['agent_settings'])['approval_mode'],'manual')
    def test_deferred_change_applies_after_native_mission(self):
        self.s.action('approval_settings',{'conversation_id':self.c,'mode':'auto'})
        results=[]
        def run(prompt,root,model,native,control):
            response=control.plugin_call('cyai_call',{'action':'update_project','arguments':{'id':self.p,'name':'Renamed'}})
            results.append(json.loads(response['content'][0]['text']))
            return 'Done'
        self.fixture.connectors['alpha'].run=run
        mission=self.s.action('create_mission',self.fixture.spec())['mission_id']
        self.fixture.wait(mission,'succeeded')
        deadline=time.monotonic()+3
        while self.s.project(self.p)['name']!='Renamed' and time.monotonic()<deadline:time.sleep(.01)
        self.assertEqual(self.s.project(self.p)['name'],'Renamed')
        self.assertEqual(self.call('job_status',{'id':results[0]['job_id']})['status'],'succeeded')
        self.assertFalse(self.s.plugins.grants)
    @unittest.skipUnless(shutil.which('node'),'Node required for real stdio transport')
    def test_real_node_stdio_http_transport(self):
        server,_=make_server(self.s,0);self.s.config['port']=server.server_port
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        config=self.s.plugins.native_config(self.p,self.control)['cyai_plugins']
        rpc=JsonProcess([config['command'],*config['args']],str(self.fixture.root),self.control,config['env'])
        try:
            self.assertIn('resources',rpc.request('initialize',{})['capabilities'])
            tools=rpc.request('tools/list',{})['tools'];self.assertIn('cyai_call',{t['name'] for t in tools})
            value=rpc.request('tools/call',{'name':'cyai_call','arguments':{'action':'save_memory','arguments':{'project_id':self.p,'content':'Written over MCP'}}})
            self.assertFalse(value['isError']);self.assertEqual(self.s.memory(self.p)[0]['content'],'Written over MCP')
            uri=rpc.request('resources/list',{})['resources'][0]['uri']
            self.assertTrue(rpc.request('resources/read',{'uri':uri})['contents'])
            self.s.plugins.grants.clear()
            with self.assertRaises(RuntimeError):rpc.request('tools/list',{})
        finally:rpc.close();server.shutdown();server.server_close()
