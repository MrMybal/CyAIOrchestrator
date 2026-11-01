"""Read-only end-to-end plugin broker check against local CyProjectCodex."""
import json
from pathlib import Path
import sys
import tempfile
import threading
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cyai.connectors import Control
from cyai.plugins import MCPProcess
from cyai.engine import Engine
from cyai.service import Service
from cyai.store import Store
from cyai.security import PathPolicy
from cyai.server import make_server

class Secrets:
    def redact(self,value):return value

with tempfile.TemporaryDirectory() as directory:
    root=Path(directory)
    store=Store(root/'test.sqlite3')
    engine=Engine(store,{},PathPolicy([root]),Secrets())
    service=Service(store,engine,{'allowed_roots':[directory]},root/'config.json')
    local=service.action('create_project',{'name':'Plugin test','root':directory})['id']
    service.plugins.config['plugins']['cyprojectcodex']['enabled']=True
    discovered=service.plugins.read('cyprojectcodex',local,'list_projects',{},discovery=True)
    projects=json.loads(discovered['content'][0]['text'])['projects']
    if not projects:raise RuntimeError('Aucun projet dans CyProjectCodex pour vérifier la lecture bornée.')
    service.plugins.bind({'id':'cyprojectcodex','project_id':local,'enabled':True,'external_project_id':projects[0]['id'],'auto_memory':False})
    server,_=make_server(service,0)
    service.config['port']=server.server_port
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    cfg=service.plugins.native_config(local)['cyai_plugins']
    rpc=MCPProcess([cfg['command'],*cfg['args']],directory,Control(60,lambda _:False,lambda *_:None),cfg['env'])
    try:
        rpc.request('initialize',{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'test','version':'1'}})
        rpc.send({'method':'notifications/initialized'})
        tools=rpc.request('tools/list',{})['tools']
        result=rpc.request('tools/call',{'name':'read_plugin','arguments':{'plugin':'cyprojectcodex','tool':'get_project','arguments':{'projectId':'wrong-scope'}}})
        outer=json.loads(result['content'][0]['text'])
        value=json.loads(outer['content'][0]['text'])
        assert value['project']['id']==projects[0]['id']
        assert len(value['projects'])==1
        print(json.dumps({'broker_tools':len(tools),'real_mcp_read':'passed','project_scope_override':'passed'}))
    finally:
        rpc.close();server.shutdown();server.server_close();thread.join();engine.shutdown();store.close()
