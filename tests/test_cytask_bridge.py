import copy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
import tempfile
import threading
from types import SimpleNamespace
import unittest

from cyai.plugins import Plugins


@unittest.skipUnless(shutil.which('node'),'Node.js is required for the official CyTask bridge')
class CyTaskBridgeTests(unittest.TestCase):
    def test_official_bridge_lists_tools_and_reads_projects_without_write_access(self):
        calls=[]
        class API(BaseHTTPRequestHandler):
            def do_GET(self):
                calls.append((self.path,self.headers.get('Authorization')=='Bearer cytask_pat_test'))
                body=json.dumps({'projects':[{'id':'fixture','name':'Fixture project'}]}).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),API)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory() as tmp:
                service=SimpleNamespace(config={},config_path=Path(tmp)/'config.json',engine=SimpleNamespace(secrets=SimpleNamespace(get=lambda k:'cytask_pat_test')))
                plugins=Plugins(service)
                p=plugins.config['plugins']['cytask'];p['enabled']=True;p['env']['CYTASK_URL']='http://127.0.0.1:'+str(server.server_port)
                try:
                    catalog=plugins.rpc(p,'tools/list',{})['tools']
                    by_name={t['name']:t for t in catalog}
                    self.assertTrue(by_name['cytask_list_projects']['annotations']['readOnlyHint'])
                    self.assertFalse(by_name['cytask_create_task']['annotations']['readOnlyHint'])
                    self.assertNotIn('cytask_create_task',p['read_tools'])
                    result=plugins.read('cytask',None,'cytask_list_projects',{})
                    self.assertEqual(result['structuredContent']['projects'][0]['name'],'Fixture project')
                    self.assertEqual(calls,[('/api/v1/projects',True)])
                    with self.assertRaises(ValueError):plugins.read('cytask',None,'cytask_create_task',{})
                finally:plugins.close_cytools()
        finally:
            server.shutdown();server.server_close();thread.join(5)
