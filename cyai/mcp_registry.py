"""Local MCP registrations shared by settings and conversation tools."""
import hashlib
import json
from pathlib import Path


def register(service,data):
    config=data['config']
    servers=config.get('mcpServers',config.get('mcp_servers',{}))
    if len(servers)!=1:raise ValueError('Fournissez un seul serveur MCP dans mcpServers.')
    label,server=next(iter(servers.items()))
    name=str(data.get('name') or label).strip()
    identifier='local-mcp-'+hashlib.sha256(name.encode()).hexdigest()[:16]
    if identifier in service.plugins.config['plugins']:raise ValueError('Ce MCP est déjà enregistré : ouvrez sa configuration.')
    project=data.get('project_id')
    if project:service.project(project)
    manifest={'id':identifier,'name':name,'type':'mcp','local_registry':True,'enabled':True,'read_tools':[],
              'instructions':str(data.get('instructions','')),'projects':{project:{'enabled':True}} if project else {}}
    token=''
    if server.get('url'):
        manifest.update(transport='http',url=server['url'])
        headers=server.get('headers',{})
        auth=next((v for k,v in headers.items() if k.lower()=='authorization'),'')
        if any(k.lower()!='authorization' for k in headers):raise ValueError('Seul Authorization Bearer est pris en charge pour HTTP.')
        if auth:
            if not auth.startswith('Bearer '):raise ValueError('Authorization Bearer requis.')
            token=auth[7:]
    else:
        command=server.get('command','')
        if not isinstance(command,str) or not command.strip():raise ValueError('Commande MCP requise.')
        cwd=server.get('cwd') or str(service.config_path.parent)
        if not Path(cwd).is_absolute() or not Path(cwd).is_dir():raise ValueError('Dossier de travail absolu existant requis.')
        env=server.get('env',{})
        if not isinstance(env,dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in env.items()):raise ValueError('Variables MCP invalides.')
        manifest.update(transport='stdio',command=command,args=server.get('args',[]),cwd=cwd,env=env)
    service.plugins.save({'manifest':manifest,'token':token})
    return {'id':identifier,'name':name,'project_id':project,'notice':'MCP enregistré, sans lancement. Utiliser mcp_local_test puis plugin_catalog et plugin_call pour ses outils.'}


def test(service,data):
    plugin=service.plugins.plugin(data['id'],data.get('project_id'))
    try:
        tools=service.plugins.rpc(plugin,'tools/list',{}).get('tools',[])
        result={'ok':True,'tools':[{'name':t['name'],'description':t.get('description','')} for t in tools]}
    except Exception as exc:result={'ok':False,'error':str(exc),'tools':[]}
    return result
