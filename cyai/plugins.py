"""Declarative extensions, project-scoped read-only MCP and annotation handoff."""
import json
import os
from pathlib import Path
import secrets
import threading
import atexit
from copy import deepcopy
import shutil
import subprocess
import urllib.request
import urllib.parse
import zipfile

from .connectors import JsonProcess, Control, executable
from .store import uid, now
from .security import scoped_path


CYAICODEX_READ_TOOLS = ['get_context','search_skills','get_skill','search_images','get_image','view_image','get_setup_guide','search_methods','get_method']
CYTASK_READ_TOOLS = ['cytask_agent_context','cytask_list_projects','cytask_list_tasks','cytask_get_task','cytask_list_agents','cytask_list_notifications']
DEFAULTS = [
    {'id':'cymd','name':'CyMD','type':'document','enabled':True,'button':'Ouvrir CyMD','source_repo':'CyMD','version':'0.1.4'},
    {'id':'cyannota','name':'CyAnnota','type':'annotation','enabled':True,'button':'Annoter des médias','source_repo':'CyAnnota','version':'0.4.4'},
    {'id':'cyaicodex','name':'CyAICodex','type':'mcp','enabled':False,'button':'Consulter les skills et images',
     'source_repo':'CyAICodex','transport':'http','url':'http://127.0.0.1:8765/mcp','web_url':'http://127.0.0.1:8765/',
     'read_tools':CYAICODEX_READ_TOOLS,'project_tab':True,
     'instructions':'At the start of a task, consult CyAICodex: get_context, search_skills, then get_skill. Respect its connection scope. Images are available through search_images, get_image and view_image. Save or update library content only when the user requests it.'},
    {'id':'cytask','name':'CyTask','type':'mcp','enabled':False,'button':'Consulter CyTask','source_repo':'CyTask',
     'transport':'stdio','command':shutil.which('node') or 'node',
     'args':[str(Path(__file__).with_name('integrations')/'cytask'/'integrations/mcp/cytask-mcp.mjs')],
     'env':{'CYTASK_URL':'http://127.0.0.1:8080'},'token_env':'CYTASK_TOKEN','read_tools':CYTASK_READ_TOOLS,'project_tab':True,
     'instructions':'CyTask provides task hierarchy, agent context and durable notifications. Discover cytask_* tools. Writes follow the conversation approval policy; server-side token permissions still apply.'}]
LEGACY_DEFAULTS = [
    {'id':'cyprojectcodex','name':'CyProjectCodex','type':'mcp','enabled':False,'button':'Bible du projet',
     'transport':'stdio','command':'node','args':[],
     'read_tools':['list_projects','get_project','search_elements'],'project_parameter':'projectId'}]



class MCPProcess(JsonProcess):
    def send(self, value):
        super().send({'jsonrpc':'2.0',**value})


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Redirection MCP refusée. Configurez son adresse locale exacte.')


class Plugins:
    def __init__(self, service):
        self.service = service
        self.config = service.config
        self.config.setdefault('plugins', {})
        for entry in DEFAULTS:
            self.config['plugins'].setdefault(entry['id'],deepcopy(entry))
        for entry in DEFAULTS[:2]:
            self.config['plugins'][entry['id']].update(version=entry['version'],source_repo=entry['source_repo'])
        codex=self.config['plugins']['cyaicodex']
        if set(codex.get('read_tools',[])) <= {'get_context','search_methods','get_method'}:
            codex['read_tools']=list(CYAICODEX_READ_TOOLS)
        codex.setdefault('source_repo','CyAICodex')
        codex.setdefault('project_tab',True)
        if not codex.get('instructions'):codex['instructions']=DEFAULTS[2]['instructions']
        if codex.get('button')=='Consulter les méthodes':codex['button']='Consulter les skills et images'
        if 'cyprojectcodex' in self.config['plugins']:
            self.config['plugins']['cyprojectcodex'].setdefault('project_tab',True)
        self.persistence_lock=threading.RLock()
        self.grants = {}
        self.cytools_sessions = {}
        self.cytools_lock = threading.RLock()
        atexit.register(self.close_cytools)

    def close_cytools(self, identifier=None):
        with self.cytools_lock:
            ids = [key for key in self.cytools_sessions if key.split(':',1)[0]==identifier] if identifier else list(self.cytools_sessions)
            for key in ids:
                entry = self.cytools_sessions.pop(key, None)
                if entry:
                    if entry.get('rpc'):
                        entry['rpc'].control.cancelled.set()
                        with entry['lock']:
                            if entry.get('rpc'): entry['rpc'].close()

    def import_cytool(self, data):
        manifest = data.get('manifest', {})
        if manifest.get('schemaVersion') != 1 or manifest.get('protocolVersion') != '1.0':
            raise ValueError('CyTool.json version 1 / protocole 1.0 requis.')
        import re
        identifier = manifest.get('id', '')
        if not isinstance(identifier,str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_.-]{0,127}',identifier):
            raise ValueError('Identifiant CyTool invalide.')
        if 'MCP' not in manifest.get('interfaces',[]):raise ValueError('Ce CyTool ne déclare pas une interface MCP.')
        # Do not execute the manifest executable string: use the explicit reviewed command.
        command, args = data.get('command',''), data.get('args',[])
        if not command or not isinstance(args,list) or not all(isinstance(a,str) for a in args) or not args or args[-1]!='mcp':
            raise ValueError('Indiquez la commande et les arguments JSON terminés par mcp.')
        root=Path(data.get('cwd',''))
        if not root.is_absolute() or not root.is_dir():raise ValueError('Dossier absolu du CyTool requis.')
        import hashlib
        plugin_id='cytool-'+hashlib.sha256(identifier.encode()).hexdigest()[:20]
        existing=self.config['plugins'].get(plugin_id,{})
        if existing and not data.get('replace'):raise ValueError('Ce CyTool est déjà enregistré. Utilisez sa configuration.')
        return self.save({'manifest':{'id':plugin_id,'name':manifest.get('name') or identifier,'type':'mcp','transport':'stdio',
            'command':command,'args':args,'env':data.get('env',{}),'cwd':str(root),'cytools':True,'cytools_id':identifier,
            'version':manifest.get('version',''),'description':manifest.get('description',''),'source_repo':data.get('source_repo',''),
            'instructions':'CyTools : op_* retourne un jobId. Suivre cy_get_job et son champ state jusqu’à Completed, Failed ou Cancelled ; transmettre progression et erreurs. Failed est un échec métier. Ne pas relancer une opération après une perte de connexion sans vérifier les jobs existants.',
            'read_tools':['cy_describe','cy_status','cy_list_jobs','cy_get_job','cy_events','cy_can_run'], 'projects':existing.get('projects',{}),
            'enabled':existing.get('enabled',True)}})

    def cytools_rpc(self, p, method, params):
        with self.cytools_lock:
            entry=self.cytools_sessions.setdefault(p['id']+':'+p.get('_cytools_scope','global'),{'lock':threading.RLock(),'rpc':None})
        with entry['lock']:
            rpc=entry['rpc']
            if rpc is None:
                rpc=MCPProcess(executable(p['command'])+p.get('args',[]),p['cwd'],Control(0,lambda _:False,lambda *_:None),env=self.process_env(p))
                entry['rpc']=rpc
                try:
                    rpc.request('initialize',{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'CyAI-CyTools','version':'1'}})
                    rpc.send({'method':'notifications/initialized'})
                except Exception:
                    entry['rpc']=None
                    rpc.close();raise
                entry['rpc']=rpc
            # Keep the process/session alive across op_* and job polling calls.
            # Never replay an operation automatically after a transport error.
            try:return rpc.request(method,params)
            except Exception:
                if rpc.proc.poll() is not None or rpc.control.cancelled.is_set():
                    entry['rpc']=None
                    rpc.close()
                raise

    def process_env(self,p):
        env={**os.environ,**p.get('env',{})}
        if p.get('token_env'):
            token=self.service.engine.secrets.get('plugin:'+p['id'])
            if isinstance(token,str) and token:env[p['token_env']]=token
        return env

    def persist(self):
        with self.persistence_lock:
            path=self.service.config_path
            temporary=path.with_name(path.name+'.'+secrets.token_hex(6)+'.tmp')
            try:
                temporary.write_text(json.dumps(self.config,ensure_ascii=False,indent=2),encoding='utf-8')
                os.replace(temporary,path)
            finally:temporary.unlink(missing_ok=True)

    def list(self, project=None):
        from .extension_catalog import legacy_replacement
        return [{**p,'binding':p.get('projects',{}).get(project,{}),'legacy_replacement':legacy_replacement(p)} for p in self.config['plugins'].values()]

    def save(self, data):
        p = dict(data['manifest'])
        imported = data.get('mcp_config','').strip()
        if imported:
            try:
                config = json.loads(imported)
                servers = config.get('mcpServers', config.get('mcp_servers',{}))
                if len(servers) != 1: raise ValueError('Collez la configuration d’un seul serveur MCP.')
                server = next(iter(servers.values()))
                if server.get('url'):
                    p.update(transport='http',url=server['url'])
                    headers=server.get('headers',{})
                    auth=next((v for k,v in headers.items() if k.lower()=='authorization'),'')
                    if auth:
                        if not auth.startswith('Bearer '): raise ValueError('Authentification Bearer requise.')
                        data={**data,'token':auth[7:]}
                    if any(k.lower()!='authorization' for k in headers): raise ValueError('Seul l’en-tête Authorization est pris en charge.')
                else: p.update(transport='stdio',command=server['command'],args=server.get('args',[]),env=server.get('env',{}),cwd=server.get('cwd',p.get('cwd',str(self.service.config_path.parent))))
            except (KeyError,TypeError,json.JSONDecodeError): raise ValueError('Configuration MCP JSON invalide.')
        if p.get('web_url'):
            url=urllib.parse.urlparse(p['web_url'])
            if url.scheme not in {'http','https'} or not url.hostname or url.username or url.password: raise ValueError('Adresse web invalide.')
        p.pop('headers',None)
        if not isinstance(p.get('env',{}),dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in p.get('env',{}).items()):raise ValueError('Variables MCP invalides.')
        if not isinstance(p.get('id'),str) or not p['id'].replace('-','').replace('_','').isalnum():
            raise ValueError('Identifiant de plugin invalide.')
        if p.get('type') not in {'annotation','mcp','document'} or not isinstance(p.get('name'),str):
            raise ValueError('Manifeste : name et type annotation ou mcp requis.')
        if p['type']=='document' and p['id']!='cymd':
            raise ValueError('Seul le plugin document CyMD intégré est pris en charge.')
        if p['type']=='mcp':
            if p.get('transport')=='http':
                parsed=urllib.parse.urlparse(p.get('url',''))
                if parsed.scheme!='http' or parsed.hostname not in {'localhost','127.0.0.1'} or parsed.username or parsed.password:
                    raise ValueError('Les plugins HTTP doivent utiliser une adresse locale sans identifiant dans l’URL.')
            elif p.get('transport')=='stdio':
                if not isinstance(p.get('command'),str) or not isinstance(p.get('args',[]),list) or any(not isinstance(a,str) for a in p.get('args',[])):
                    raise ValueError('Commande et arguments MCP invalides.')
            else:
                raise ValueError('Transport MCP : http ou stdio.')
            if not isinstance(p.get('read_tools'),list) or any(not isinstance(x,str) for x in p['read_tools']):
                raise ValueError('Déclarez les outils de lecture dans read_tools.')
        if p.get('cytools'):
            if not isinstance(p.get('env',{}),dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in p.get('env',{}).items()):raise ValueError('Variables MCP invalides.')
            if p.get('transport')!='stdio' or not Path(p.get('cwd','')).is_absolute() or not Path(p['cwd']).is_dir():
                raise ValueError('CyTools : dossier absolu existant et transport stdio requis.')
            if not p.get('args') or p['args'][-1]!='mcp':raise ValueError('Les arguments CyTools doivent se terminer par mcp.')
        token_env=p.get('token_env') or ('CYTASK_TOKEN' if p.get('id')=='cytask' else 'CYTOOLS_TOKEN' if p.get('cytools') else '')
        if token_env:
            import re
            if not re.fullmatch('[A-Z][A-Z0-9_]{0,79}',token_env):raise ValueError('Nom de variable de jeton invalide.')
            p['token_env']=token_env
            p['env']=dict(p.get('env',{}))
            if p['env'].get(token_env):data={**data,'token':p['env'].pop(token_env)}
        p.pop('token',None)
        self.close_cytools(p['id'])
        self.config['plugins'][p['id']] = p
        if data.get('token'):
            self.service.engine.secrets.set('plugin:'+p['id'],data['token'])
        self.persist()
        return {'ok':True}

    def plugin(self, id, project=None):
        p=self.config['plugins'].get(id)
        if not p or not p.get('enabled'):
            raise ValueError('Plugin absent ou désactivé.')
        if project:
            self.service.store.one('SELECT id FROM projects WHERE id=?',(project,))
            if p.get('projects',{}).get(project,{}).get('enabled',not p.get('local_registry',False)) is False:
                raise ValueError('Plugin désactivé pour ce projet.')
        return p

    def rpc(self, p, method, params):
        if p.get('cytools'):
            result=self.cytools_rpc(p,method,params)
        elif p['transport']=='stdio':
            args=executable(p['command'])+p.get('args',[])
            rpc=MCPProcess(args,p.get('cwd') or str(self.service.config_path.parent),Control(25,lambda _:False,lambda *_:None),env=self.process_env(p))
            try:
                rpc.request('initialize',{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'cyai-plugins','version':'1'}})
                rpc.send({'method':'notifications/initialized'})
                result=rpc.request(method,params)
            finally:
                rpc.close()
        else:
            token=self.service.engine.secrets.get('plugin:'+p['id'])
            headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream'}
            if token: headers['Authorization']='Bearer '+token
            def request(name,args,id=1):
                payload={'jsonrpc':'2.0','method':name,'params':args}
                if id is not None: payload['id']=id
                req=urllib.request.Request(p['url'],data=json.dumps(payload).encode(),headers=headers)
                with urllib.request.build_opener(NoRedirect).open(req,timeout=20) as response:
                    if response.headers.get('Mcp-Session-Id'):headers['Mcp-Session-Id']=response.headers['Mcp-Session-Id']
                    raw=response.read(16*1024**2+1)
                    if len(raw)>16*1024**2:raise ValueError('Réponse MCP trop grande.')
                    if not raw:return {}
                    text=raw.decode('utf-8')
                    if 'text/event-stream' in response.headers.get('Content-Type',''):
                        values=[json.loads(line[5:].strip()) for line in text.splitlines() if line.startswith('data:')]
                        return next((v for v in values if v.get('id')==id),{})
                    return json.loads(text)
            init=request('initialize',{'protocolVersion':'2025-06-18','capabilities':{},'clientInfo':{'name':'cyai-plugins','version':'1'}})
            if init.get('error'):raise ValueError(str(init['error']))
            headers['MCP-Protocol-Version']=init.get('result',{}).get('protocolVersion','2025-06-18')
            request('notifications/initialized',{},None)
            envelope=request(method,params,2)
            if envelope.get('error'):raise ValueError(str(envelope['error']))
            result=envelope.get('result',{})
        if result.get('isError'):raise ValueError('Le serveur MCP a refusé la lecture : '+str(result.get('content',''))[:1000])
        return result

    def catalog(self, id):
        p=self.plugin(id)
        tools=self.rpc(p,'tools/list',{}).get('tools',[])
        tools=[t for t in tools if t['name'] in p.get('read_tools',[])]
        try: resources=[] if p.get('cytools') else self.rpc(p,'resources/list',{}).get('resources',[])
        except Exception: resources=[]
        return {'tools':tools,'resources':resources}

    def read(self, id, project, tool=None, arguments=None, resource=None, discovery=False):
        p=self.plugin(id,project)
        if resource:
            if p.get('project_parameter'):
                raise ValueError('Utilisez les outils bornés au projet pour cette bible.')
            known=self.catalog(id)['resources']
            if resource not in [r['uri'] for r in known]:raise ValueError('Ressource non annoncée par le serveur.')
            return self.rpc(p,'resources/read',{'uri':resource})
        if tool not in p.get('read_tools',[]):raise ValueError('Outil non autorisé en lecture.')
        args=dict(arguments or {})
        binding=p.get('projects',{}).get(project,{})
        if p.get('project_parameter'):
            if tool=='list_projects':
                if not discovery:raise ValueError('La découverte des projets est réservée à la configuration utilisateur.')
            else:
                external=binding.get('external_project_id')
                if not external:raise ValueError('Associez ce projet à son identifiant dans CyProjectCodex.')
                args[p['project_parameter']]=external
        result=self.rpc(p,'tools/call',{'name':tool,'arguments':args})
        if p.get('project_parameter') and tool!='list_projects':
            for block in result.get('content',[]):
                if block.get('type')=='text':
                    try:
                        value=json.loads(block['text'])
                        if isinstance(value,dict) and 'projects' in value:
                            value['projects']=[x for x in value['projects'] if x.get('id')==binding.get('external_project_id')]
                            block['text']=json.dumps(value,ensure_ascii=False)
                    except (ValueError,TypeError):pass
        serialized=json.dumps(result,ensure_ascii=False)
        if len(serialized)>(16*1024**2 if any(b.get('type')=='image' for b in result.get('content',[])) else 100000):raise ValueError('Résultat trop volumineux ; utilisez une recherche plus précise.')
        return result

    def web_url(self, id):
        p=self.config['plugins'].get(id)
        if not p:raise ValueError('Plugin inconnu.')
        url=p.get('web_url') or {'cyaicodex':'http://127.0.0.1:8765/','cytask':p.get('env',{}).get('CYTASK_URL','http://127.0.0.1:8080/'),'cyprojectcodex':'http://127.0.0.1:4310/'}.get(id,'')
        parsed=urllib.parse.urlparse(url)
        if parsed.scheme not in {'http','https'} or not parsed.hostname or parsed.username or parsed.password:raise ValueError('Adresse web invalide.')
        return {'url':url}

    def create_project(self, data):
        p=self.plugin(data['id'],data['project_id'])
        if p['id']!='cyprojectcodex': raise ValueError('Création réservée à CyProjectCodex.')
        name=str(data.get('name','')).strip()
        if not name or len(name)>200: raise ValueError('Nom de projet requis (200 caractères maximum).')
        result=self.rpc(p,'tools/call',{'name':'create_project','arguments':{'name':name,'description':str(data.get('description',''))[:4000]}})
        value=json.loads(next(b['text'] for b in result.get('content',[]) if b.get('type')=='text'))
        external=value.get('id') or value.get('project',{}).get('id')
        if not external: raise ValueError('Projet créé mais identifiant non reçu. Choisissez-le dans les associations existantes.')
        self.bind({'id':p['id'],'project_id':data['project_id'],'external_project_id':external})
        return {'external_project_id':external}

    def bind(self, data):
        p=self.config['plugins'][data['id']]
        self.service.store.one('SELECT id FROM projects WHERE id=?',(data['project_id'],))
        binding=p.setdefault('projects',{}).setdefault(data['project_id'],{})
        if data.get('external_project_id') and p.get('project_parameter'):
            result=self.rpc(p,'tools/call',{'name':'list_projects','arguments':{}})
            value=json.loads(next(b['text'] for b in result.get('content',[]) if b.get('type')=='text'))
            external=next((x for x in value.get('projects',[]) if x['id']==data['external_project_id']),None)
            if not external: raise ValueError('Projet externe introuvable. Actualisez la liste.')
            binding['external_project_name']=external.get('name',external['id'])
        if 'external_project_id' in data and not data['external_project_id']: binding.pop('external_project_name',None)
        binding.update({k:data[k] for k in ('external_project_id','auto_memory','enabled') if k in data})
        self.persist()
        return {'ok':True}

    def context(self, project):
        result=[]
        for p in self.list(project):
            if p.get('legacy_replacement'):continue
            if p.get('enabled') and p['binding'].get('enabled',True) is not False and p.get('instructions'):
                result.append({'plugin':p['name'], 'content':p['instructions'][:8000]})
            if p.get('enabled') and p['binding'].get('enabled',True) is not False and p['binding'].get('auto_memory'):
                value=self.read(p['id'],project,'get_project',{})
                text=json.dumps(value,ensure_ascii=False)
                if len(text)>16000:raise ValueError('Mémoire structurée trop grande. Désactivez son ajout automatique et consultez des fiches via le plugin.')
                result.append({'plugin':p['name'],'content':text})
        return result

    def native_config(self, project, control=None, helpers=None, root=None, packs=None):
        token=secrets.token_urlsafe(32)
        self.grants[token]={"projects":[project],"control":control,"helpers":helpers or [],"root":root,"calls":0,"packs":packs or []}
        return {'cyai_plugins':{'command':shutil.which('node') or 'node','args':[str(Path(__file__).with_name('plugin_bridge.mjs'))],
            'env':{'CYAI_PLUGIN_URL':f"http://127.0.0.1:{self.config.get('port',8766)}/api/plugin-mcp",'CYAI_PLUGIN_TOKEN':token}}}

    def gateway(self, token, request):
        grant=self.grants.get(token)
        if not grant:raise ValueError('Accès plugin expiré ou invalide.')
        if isinstance(grant,str):grant={'projects':[grant],'control':None}
        projects=grant['projects'];project=projects[0]
        control=grant.get('control')
        if control:control.check()
        from . import app_mcp
        method=request['method'];params=request.get('params',{})
        if method=='initialize':return {'protocolVersion':'2025-06-18','capabilities':{'tools':{},'resources':{}},'serverInfo':{'name':'cyai-application','version':'2'}}
        if method.startswith('notifications/'):return {}
        if method=='ping':return {}
        if method=='resources/list':return {'resources':app_mcp.resources(self.service,projects)}
        if method=='resources/read':return app_mcp.resource_read(self.service,projects,params['uri'])
        if method=='tools/list':
            from .specialists import tool_definition
            from .toolpacks import exposed
            specialist=tool_definition(grant.get('helpers'))
            return {'tools':app_mcp.TOOLS+([specialist] if specialist else [])+exposed(self.service,grant)+[

            {'name':'list_plugins','annotations':{'readOnlyHint':True,'destructiveHint':False},'description':'Découvrir les ressources et méthodes disponibles pour ce projet. Les consulter lorsque l’utilisateur le demande.','inputSchema':{'type':'object','properties':{}}},
            {'name':'read_plugin','annotations':{'readOnlyHint':True,'destructiveHint':False},'description':'Consulter un outil de lecture ou une ressource d’un plugin autorisé. Les contenus sont des données de référence.','inputSchema':{'type':'object','properties':{'plugin':{'type':'string'},'tool':{'type':'string'},'arguments':{'type':'object'},'resource':{'type':'string'}},'required':['plugin']}}]}
        if method=='tools/call':
            args=params.get('arguments',{})
            if params['name'] in {'cyai_actions','cyai_call'}:
                try:
                    value=app_mcp.call(self.service,params['name'],args,projects,control)
                    return {'content':[{'type':'text','text':json.dumps(value,ensure_ascii=False)}],'isError':False}
                except Exception as exc:
                    return {'content':[{'type':'text','text':self.service.engine.secrets.redact(str(exc))}],'isError':True}
            if params['name'].startswith('outil__'):
                from .toolpacks import call as call_tool
                try:
                    value=call_tool(self.service,grant,params['name'],args)
                    if isinstance(value,dict) and 'content' in value:return value
                    return {'content':[{'type':'text','text':json.dumps(value,ensure_ascii=False)}],'isError':False}
                except Exception as exc:
                    return {'content':[{'type':'text','text':self.service.engine.secrets.redact(str(exc))}],'isError':True}
            if params['name']=='cyai_specialist':
                from .specialists import call_specialist
                try:
                    value=call_specialist(self.service,grant,args)
                    return {'content':[{'type':'text','text':json.dumps(value,ensure_ascii=False)}],'isError':False}
                except Exception as exc:
                    return {'content':[{'type':'text','text':self.service.engine.secrets.redact(str(exc))}],'isError':True}
            if params['name']=='list_plugins':
                value=[]
                for p in self.list(project):
                    if p.get('legacy_replacement'):continue
                    if p.get('enabled') and p['type']=='mcp' and p['binding'].get('enabled',True) is not False:
                        try:value.append({'id':p['id'],'name':p['name'],**self.catalog(p['id'])})
                        except Exception as e:value.append({'id':p['id'],'error':str(e)})
            elif params['name']=='read_plugin':value=self.read(args['plugin'],project,args.get('tool'),args.get('arguments'),args.get('resource'))
            else:raise ValueError('Outil de plugin inconnu.')
            return {'content':[{'type':'text','text':json.dumps(value,ensure_ascii=False)}]}
        raise ValueError('Méthode MCP non prise en charge.')

    def annotate(self, data):
        p=self.plugin(data.get('id','cyannota'),data.get('project_id'))
        from .windows_ui import choose_file
        path=choose_file()
        if not path:return {'cancelled':True}
        if Path(path).suffix.lower() not in {'.png','.jpg','.jpeg','.webp','.bmp','.cyannota','.zip'}:raise ValueError('Choisissez une image ou un projet CyAnnota.')
        subprocess.Popen([p['executable'],path])
        return {'detail':'Image ouverte dans CyAnnota. Exportez pour IA, puis utilisez Importer les annotations dans la conversation.'}

    def import_annotations(self, conversation):
        self.plugin('cyannota')
        project=self.service.project_for_conversation(conversation)
        self.plugin('cyannota',project['id'])
        from .windows_ui import choose_file
        path=choose_file()
        if not path:return {'cancelled':True}
        dest=scoped_path(project['root'],'.cyai-annotations/'+uid(),must_exist=False)
        texts=[];images=[]
        with zipfile.ZipFile(path) as archive:
            items=archive.infolist()
            if len(items)>500 or sum(i.file_size for i in items)>50000000:raise ValueError('Archive limitée à 50 Mo et 500 entrées.')
            if not any(i.filename.endswith('/prompt.md') for i in items):raise ValueError('Aucune consigne IA dans cette archive. Exportez CyAnnota en mode IA.')
            for item in items:
                if item.filename.endswith('/prompt.md'):
                    texts.append(archive.read(item).decode('utf-8')[:100000])
                elif Path(item.filename).suffix.lower() in {'.png','.jpg','.jpeg','.webp'} and '/images/' in item.filename:
                    dest.mkdir(parents=True,exist_ok=True)
                    target=dest/(str(len(images))+'-'+Path(item.filename).name)
                    target.write_bytes(archive.read(item));images.append(str(target))
        if not texts:raise ValueError('Aucune consigne IA dans cette archive. Exportez CyAnnota en mode IA.')
        content='\n\n'.join(texts)+'\n\nImages locales à consulter avec un agent capable de lire les images :\n'+'\n'.join(images)
        id=uid();self.service.store.execute('INSERT INTO files VALUES(?,?,?,?,?,?)',(id,conversation,'Annotations CyAnnota',content,'annotation',now()))
        return {'id':id,'images':len(images)}
