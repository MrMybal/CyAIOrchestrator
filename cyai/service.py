"""Application use cases. No HTTP or UI dependencies."""
import json
from pathlib import Path

from .context import build_context
from .engine import ACTIVE
from .security import scoped_path, scoped_workspace, PathPolicy
from .store import now, uid
from .planning import planning_instruction

TABLES = ["projects", "conversations", "messages", "sessions", "missions", "steps", "events", "memory", "files"]
# Global agent library and per-project teams. Added in backup format 2; format 1 archives stay restorable.
TEAM_TABLES = ["agent_profiles", "agent_profile_revisions", "teams", "team_members", "team_templates", "tasks", "task_reports", "task_consultations", "task_executions", "agent_memory", "task_evaluations", "improvement_proposals", "method_templates", "method_revisions", "method_assets", "profile_methods", "method_tests", "method_runs", "method_loops", "method_chains", "method_proposals", "member_assessments", "skill_attestations", "project_spaces", "agent_benchmarks"]


class Service:
    def __init__(self, store, engine, config, config_path):
        self.store, self.engine, self.config, self.config_path = store, engine, config, Path(config_path)
        self.engine.approval_default = config.get("approval_default", "manual")
        self.engine.access_default = config.get("agent_access_default", "project")
        from .app_mcp import init_jobs
        init_jobs(self)
        from .conversation_queue import init as init_outbox
        init_outbox(self)
        from .free_workspaces import migrate_legacy
        migrate_legacy(self)
        from .resource_usage import ResourceUsage
        self.resources = ResourceUsage(self)
        self.health = {}
        self.catalogs = dict(config.get('models_cache',{}))
        from .autopilot import stop_after_restart
        stop_after_restart(self)
        from .method_lab import stop_after_restart as stop_loops_after_restart
        stop_loops_after_restart(self)
        from .plugins import Plugins
        self.plugins = Plugins(self)
        self.engine.plugins = self.plugins
        from .extension_catalog import ExtensionCatalog
        self.extensions = ExtensionCatalog(self)
        from .optional_components import OptionalComponents
        self.components = OptionalComponents(self)
        if 'local' in self.engine.connectors:
            from .local_models import LocalModels
            self.local_models = LocalModels(self)
            self.engine.connectors['local'].manager = self.local_models
            self.engine.local_models = self.local_models
            from .connector_health import start_probes
            start_probes(self)
        # The voice starts switched off; only a click of the user turns the microphone or the reading on.
        from .voice import Voice
        self.voice = Voice(self)
        self.engine.voice = self.voice
        self.store.log('info','service.start','Service local prêt.')

    def logs(self, query):
        level=query.get('level','');source=query.get('source','');search=query.get('text','').lower()[:300]
        rows=[]
        if source in {'','application'}:
            for r in self.store.rows('SELECT * FROM app_logs ORDER BY id DESC LIMIT 1000'):
                rows.append({'id':'app:'+str(r['id']),'time':r['created_at'],'level':r['level'],'source':'application','operation':r['operation'],'detail':r['detail']})
        if source in {'','agents'}:
            for r in self.store.rows('SELECT e.*,m.title,c.project_id,p.name AS project FROM events e JOIN missions m ON m.id=e.mission_id JOIN conversations c ON c.id=m.conversation_id JOIN projects p ON p.id=c.project_id ORDER BY e.seq DESC LIMIT 1000'):
                data=json.loads(r['data'])
                severity='error' if r['kind'] in {'error','failed'} or (isinstance(data,dict) and data.get('status')=='failed') else 'info'
                rows.append({'id':'event:'+str(r['seq']),'time':r['created_at'],'level':severity,'source':'agents','operation':r['kind'],'project':r['project'],'mission':r['title'],'mission_id':r['mission_id'],'step_id':r['step_id'],'detail':data})
        rows=self.engine.secrets.redact(rows)
        rows=[r for r in rows if (not level or r['level']==level) and (not search or search in json.dumps(r,ensure_ascii=False).lower())]
        rows.sort(key=lambda r:(r['time'],r['id']),reverse=True)
        return {'entries':rows[:300],'limit':300,'notice':'300 dernières entrées correspondantes parmi les 1 000 événements récents de chaque source. Le journal application conserve 5 000 entrées ; les événements IA restent dans les missions.'}

    def project(self, id):
        project = self.store.one('SELECT * FROM projects WHERE id=?', (id,))
        project['conversations'] = self.store.rows('SELECT * FROM conversations WHERE project_id=? AND internal_parent_id IS NULL ORDER BY created_at DESC, rowid DESC', (id,))
        project['missions'] = self.store.rows('SELECT m.* FROM missions m JOIN conversations c ON m.conversation_id=c.id WHERE c.project_id=? ORDER BY m.created_at DESC LIMIT 200', (id,))
        for m in project['missions']:
            m['planning'] = bool(json.loads(m.pop('spec')).get('planning'))
        from .project_memory import project_foundation
        project['foundation'] = project_foundation(self.store,id)
        from .teams import project_team_summary
        project['team'] = project_team_summary(self.store,id)
        project['memory'] = self.store.rows('SELECT * FROM memory WHERE project_id=? ORDER BY created_at', (id,))
        project['usage'] = self.store.rows('SELECT s.connector,COALESCE((SELECT msg.model FROM messages msg WHERE msg.source_id=s.id ORDER BY msg.seq DESC LIMIT 1),s.model) AS model,s.status,s.usage FROM steps s JOIN missions m ON s.mission_id=m.id JOIN conversations c ON c.id=m.conversation_id WHERE c.project_id=?', (id,))
        project['history'] = self.store.rows('SELECT m.role,m.connector,m.model,m.created_at,c.title,c.id AS conversation_id FROM messages m JOIN conversations c ON c.id=m.conversation_id WHERE c.project_id=? ORDER BY m.seq DESC LIMIT 100', (id,))
        from .workspace import git_status
        project['git'] = git_status(project['root'])
        return project

    def project_for_conversation(self, id):
        project = self.store.one("SELECT p.* FROM projects p JOIN conversations c ON c.project_id=p.id WHERE c.id=?", (id,))
        self.engine.policy.project(project["root"])
        return project

    def state(self):
        # Local inventory is authoritative; downloads/imports must not wait for a remote catalogue probe.
        if "local" in self.engine.connectors:
            self.catalogs["local"] = self.engine.connectors["local"].models()
        with self.engine.lock:
            approvals = [{"id": id, **{k: v for k, v in a.items() if k not in {"event", "decision"}}} for id, a in self.engine.approvals.items()]
        connectors = []
        for id, connector in self.engine.connectors.items():
            try:
                status = connector.check() if id=='local' else self.health.get(id) or connector.check()
                successful = self.store.rows("SELECT m.updated_at FROM steps s JOIN missions m ON m.id=s.mission_id WHERE s.connector=? AND s.status='succeeded' ORDER BY m.updated_at DESC LIMIT 1", (id,))
                if successful and id not in self.health and id!='local':
                    status = {**status, "status": "operational", "detail": "Dernière exécution réussie : " + successful[0]["updated_at"]}
            except Exception as e:
                status = {"status": "error", "detail": self.engine.secrets.redact(str(e))}
            connectors.append({"id": id, "kind": connector.kind, "model": connector.config.get("model", ""), "executable":connector.config.get('executable',''),
                               "native_auto_approve":connector.config.get("native_auto_approve",False), "enabled": connector.config.get("enabled", False), **status})
        local = self.engine.connectors.get('local')
        local_config = local.config if local else {}
        manager = getattr(self,'local_models',None)
        local_info = {'loaded':getattr(manager,'loaded',None),'context':local_config.get('context',4096),
                      'models':[{'id':m['id'],'name':m.get('name',m['id']),'context':m.get('settings',{}).get('context',local_config.get('context',4096))} for m in local_config.get('models',[])]}
        return {"local_info":local_info,"resources":self.resources.get(),"projects": self.store.rows("SELECT * FROM projects ORDER BY favorite DESC,position,created_at"),
                "conversations": self.store.rows("SELECT * FROM conversations WHERE internal_parent_id IS NULL ORDER BY favorite DESC,position,created_at DESC"),
                "missions": self.store.rows("SELECT id,conversation_id,title,status,created_at,updated_at FROM missions ORDER BY created_at DESC LIMIT 200"),
                "connectors": connectors, "plugins":self.plugins.list(), "extension_catalog":self.extensions.state(), "approvals": approvals, "allowed_roots": [str(p) for p in self.engine.policy.roots],
                "mcp_jobs":self.store.rows("SELECT id,action,status,result,created_at,conversation_id FROM mcp_jobs ORDER BY created_at DESC LIMIT 100"), "approval_default":self.engine.approval_default, "access_default":self.engine.access_default, "models_cache":self.catalogs, "model_ratings":self.config.get("model_ratings",{}), "settings": self.config.get("settings", {}), "categories": self.config.get("categories", []), "data_dir":str(self.store.path.parent), "pending_data_dir":self.config.get("pending_data_dir", ""), "storage_error":self.config.get("storage_error", ""), "context_chars": self.engine.context_chars, "version": __import__("cyai").__version__}

    def memory(self, project_id):
        project = self.store.one("SELECT * FROM projects WHERE id=?", (project_id,))
        self.engine.policy.project(project["root"])
        return self.store.rows("SELECT * FROM memory WHERE project_id=? ORDER BY created_at", (project_id,))

    def conversation(self, id):
        self.project_for_conversation(id)
        result = self.store.one("SELECT * FROM conversations WHERE id=?", (id,))
        from .conversation_queue import rows as outbox_rows
        result['outbox'] = outbox_rows(self,id)
        result['background'] = self.store.rows("SELECT m.id,m.title,m.status,(SELECT COUNT(*) FROM steps WHERE mission_id=m.id) AS total,(SELECT COUNT(*) FROM steps WHERE mission_id=m.id AND status='succeeded') AS completed FROM missions m JOIN conversations c ON c.id=m.conversation_id WHERE c.internal_parent_id=? ORDER BY m.created_at DESC",(id,))
        for background in result['background']:
            background['steps']=self.store.rows('SELECT id,name,connector,model,status,error FROM steps WHERE mission_id=? ORDER BY position',(background['id'],))
        result["messages"] = self.store.rows("SELECT * FROM messages WHERE conversation_id=? ORDER BY seq", (id,))
        result['failures'] = self.store.rows("SELECT e.seq,e.mission_id,e.created_at,e.data FROM events e JOIN missions m ON m.id=e.mission_id WHERE m.conversation_id=? AND e.kind IN ('error','engine_error','recovery_required') ORDER BY e.seq", (id,))
        for failure in result['failures']:
            failure['data'] = json.loads(failure['data'])
        result['failures'] = [f for f in result['failures'] if f['data'].get('status', 'failed') in {'failed','interrupted'}]
        result["sessions"] = self.store.rows("SELECT * FROM sessions WHERE conversation_id=?", (id,))
        result["files"] = self.store.rows("SELECT id,name,kind,created_at,CASE WHEN kind='media' THEN content ELSE '' END AS content FROM files WHERE conversation_id=?", (id,))
        result["memory"] = self.store.rows("SELECT * FROM memory WHERE project_id=? ORDER BY created_at", (result["project_id"],))
        result['plans'] = []
        for mission in self.store.rows("SELECT id,spec FROM missions WHERE conversation_id=? AND status='succeeded' ORDER BY created_at DESC", (id,)):
            spec = json.loads(mission['spec'])
            if spec.get('proposal', {}).get('plan'):
                execution = self.store.rows('SELECT id,status,spec FROM missions WHERE request_key=?', ('plan:' + mission['id'],))
                if execution:
                    approved=json.loads(execution[0].pop('spec'))
                    spec['proposal']['plan']={'title':approved['title'],'steps':approved['steps']}
                    execution[0]['steps'] = self.store.rows('SELECT position,status FROM steps WHERE mission_id=? ORDER BY position', (execution[0]['id'],))
                result['plans'].append({'id': mission['id'], **spec['proposal'], 'execution': execution[0] if execution else None})
                break
        return result

    def mission(self, id, after=0):
        result = self.store.one("SELECT * FROM missions WHERE id=?", (id,))
        self.project_for_conversation(result["conversation_id"])
        result["spec"] = json.loads(result["spec"])
        result["steps"] = self.store.rows("SELECT * FROM steps WHERE mission_id=? ORDER BY position", (id,))
        for step in result["steps"]:
            for key in ("context", "usage"):
                step[key] = json.loads(step[key]) if step[key] else None
        result["events"] = self.store.rows("SELECT * FROM events WHERE mission_id=? AND seq>? ORDER BY seq LIMIT 1000", (id, int(after)))
        for e in result["events"]:
            e["data"] = json.loads(e["data"])
        return result

    def search(self, query):
        sql = "SELECT m.*,c.title,c.project_id FROM messages m JOIN conversations c ON c.id=m.conversation_id WHERE instr(lower(m.content),lower(?))>0"
        params = [query.get("text", "")]
        for key, column in (("project_id", "c.project_id"), ("connector", "m.connector")):
            if query.get(key):
                sql += f" AND {column}=?"
                params.append(query[key])
        if query.get("date_from"):
            sql += " AND m.created_at>=?"
            params.append(query["date_from"])
        if query.get("date_to"):
            sql += " AND m.created_at<=?"
            params.append(query["date_to"] + "T23:59:59.999Z")
        if query.get("status"):
            sql += " AND EXISTS(SELECT 1 FROM missions x WHERE x.conversation_id=c.id AND x.status=?)"
            params.append(query["status"])
        rows = self.store.rows(sql + " ORDER BY m.seq DESC LIMIT 100", params)
        authorized = []
        for row in rows:
            try:
                self.project_for_conversation(row["conversation_id"])
                authorized.append(row)
            except (ValueError, OSError):
                pass
        return authorized

    def _idle(self, conversation_id=None):
        sql = "SELECT id FROM missions WHERE status IN ('queued','running','awaiting_approval','pausing')"
        params = ()
        if conversation_id:
            sql += " AND (conversation_id=? OR conversation_id IN (SELECT id FROM conversations WHERE internal_parent_id=?))"
            params = (conversation_id,conversation_id)
        if self.store.rows(sql, params):
            raise ValueError("Attendez la fin des missions ou annulez-les avant cette opération.")

    def free_workspace(self):
        """An isolated workspace for a discussion outside any project, with no memory or plugin inherited."""
        root=self.store.path.parent/'discussion-workspaces'/uid()
        root.mkdir(parents=True,exist_ok=False)
        project_id=self.action('create_project',{'name':'Discussion libre','root':str(root)})['id']
        self.store.execute('UPDATE projects SET free_chat=1 WHERE id=?',(project_id,))
        return project_id

    def action(self, action, data):
        if action == 'open_documentation':
            from .documentation import DocumentationLauncher
            from .i18n import language
            if not hasattr(self,'_documentation_launcher'):
                self._documentation_launcher=DocumentationLauncher(self.store.path.parent/'documentation-control')
            route={key:data[key] for key in ('page_id','anchor','state') if key in data}
            route['locale']=data.get('locale',language(self.config))
            route['theme']=data.get('theme',self.config.get('settings',{}).get('theme','dark'))
            return self._documentation_launcher.open(**route)
        if action == 'component_state': return {'items': self.components.state()}
        if action == 'component_install': return self.components.install(data.get('id', ''))
        if action.startswith('evaluation_'):
            from .agent_evaluation import handle
            return handle(self, action, data)
        if action=='resource_history':
            with self.resources.lock:return {'samples':list(self.resources.history)}
        if action=='preview_local':
            from .media import preview
            return preview(self,data)
        if action=='open_local':
            from .media import open_local
            return open_local(self,data)
        if action=='reveal_local':
            from .media import reveal
            return reveal(self,data)
        if action=='mcp_client_config':
            import sys
            project=self.store.one('SELECT * FROM projects WHERE id=?',(data['project_id'],))
            args=['--config',str(self.config_path.resolve()),'--project',project['id']]
            if data.get('allow_write'):args.append('--allow-write')
            if data.get('allow_global'):
                if not data.get('allow_write'):raise ValueError('Les écritures globales supposent aussi les écritures du projet : activez d’abord --allow-write.')
                args.append('--allow-global')
            if getattr(sys,'frozen',False):
                command=str(Path(sys.executable).parent.parent/'CyAI-MCP'/'CyAI-MCP.exe')
            else:command=sys.executable;args=['-m','cyai','mcp',*args]
            flavor=data.get('format','claude')
            if flavor=='codex':text='[mcp_servers.cyai]\ncommand = '+json.dumps(command)+'\nargs = '+json.dumps(args)+'\ntool_timeout_sec = 600\n'
            elif flavor=='opencode':text=json.dumps({'mcp':{'cyai':{'type':'local','command':[command,*args],'enabled':True,'timeout':600000}}},ensure_ascii=False,indent=2)
            else:text=json.dumps({'mcpServers':{'cyai':{'command':command,'args':args}}},ensure_ascii=False,indent=2)
            return {'text':text,'project':project['name'],'allow_write':bool(data.get('allow_write')),'allow_global':bool(data.get('allow_global'))}
        if action=='mcp_catalog':
            from .app_mcp import ACTIONS,USER_ONLY
            return {'actions':list(ACTIONS.values()),'user_only':USER_ONLY}

        if action == 'access_settings':
            # What Codex may reach beyond the project: chosen here, per conversation or by default, never by the agent.
            from .connectors import ACCESS_LEVELS
            level = data.get('level', 'project')
            if level not in ACCESS_LEVELS + ('inherit',):
                raise ValueError('Niveau d’accès invalide.')
            if data.get('conversation_id'):
                self.project_for_conversation(data['conversation_id'])
                with self.engine.lock:
                    row = self.store.one('SELECT agent_settings FROM conversations WHERE id=?', (data['conversation_id'],))
                    settings = json.loads(row['agent_settings'])
                    if level == 'inherit':
                        settings.pop('agent_access', None)
                    else:
                        settings['agent_access'] = level
                    self.store.execute('UPDATE conversations SET agent_settings=? WHERE id=?', (json.dumps(settings), data['conversation_id']))
            else:
                if level == 'inherit':
                    raise ValueError('Choisissez un niveau par défaut.')
                self.config['agent_access_default'] = level
                self.engine.access_default = level
                self.plugins.persist()
            return {'ok': True}
        if action == 'approval_settings':
            mode = data.get('mode', 'manual')
            if mode not in {'manual','auto','inherit'}: raise ValueError('Mode d’autorisation invalide.')
            if data.get('conversation_id'):
                self.project_for_conversation(data['conversation_id'])
                with self.engine.lock:
                    row = self.store.one('SELECT agent_settings FROM conversations WHERE id=?',(data['conversation_id'],))
                    settings = json.loads(row['agent_settings'])
                    if mode == 'inherit': settings.pop('approval_mode',None)
                    else: settings['approval_mode'] = mode
                    self.store.execute('UPDATE conversations SET agent_settings=? WHERE id=?',(json.dumps(settings),data['conversation_id']))
            else:
                if mode == 'inherit': raise ValueError('Choisissez un mode global.')
                self.config['approval_default'] = mode
                self.engine.approval_default = mode
                self.plugins.persist()
            return {'ok':True}

        if action.startswith('local_'):
            result = self.local_models.action(action, data)
            if result is not None: return result

        from .workspace import workspace_action, UNHANDLED
        result = workspace_action(self, action, data)
        if result is not UNHANDLED:
            return result
        from .teams import teams_action, UNHANDLED as TEAMS_UNHANDLED
        result = teams_action(self, action, data)
        if result is not TEAMS_UNHANDLED:
            return result
        from .tasks import tasks_action, UNHANDLED as TASKS_UNHANDLED
        result = tasks_action(self, action, data)
        if result is not TASKS_UNHANDLED:
            return result
        from .team_runtime import team_runtime_action, UNHANDLED as RUNTIME_UNHANDLED
        result = team_runtime_action(self, action, data)
        if result is not RUNTIME_UNHANDLED:
            return result
        from .learning import learning_action, UNHANDLED as LEARNING_UNHANDLED
        result = learning_action(self, action, data)
        if result is not LEARNING_UNHANDLED:
            return result
        from .methods import methods_action, UNHANDLED as METHODS_UNHANDLED
        result = methods_action(self, action, data)
        if result is not METHODS_UNHANDLED:
            return result
        from .model_capabilities import model_capabilities_action, UNHANDLED as CAPABILITIES_UNHANDLED
        result = model_capabilities_action(self, action, data)
        if result is not CAPABILITIES_UNHANDLED:
            return result
        from .team_lead import team_lead_action, UNHANDLED as LEAD_UNHANDLED
        result = team_lead_action(self, action, data)
        if result is not LEAD_UNHANDLED:
            return result
        from .project_assistant import project_assistant_action, UNHANDLED as ASSISTANT_UNHANDLED
        result = project_assistant_action(self, action, data)
        if result is not ASSISTANT_UNHANDLED:
            return result
        from .method_agents import method_agents_action, UNHANDLED as METHOD_AGENTS_UNHANDLED
        result = method_agents_action(self, action, data)
        if result is not METHOD_AGENTS_UNHANDLED:
            return result
        from .method_lab import method_lab_action, UNHANDLED as METHOD_LAB_UNHANDLED
        result = method_lab_action(self, action, data)
        if result is not METHOD_LAB_UNHANDLED:
            return result
        from .autopilot import autopilot_action, UNHANDLED as AUTOPILOT_UNHANDLED
        result = autopilot_action(self, action, data)
        if result is not AUTOPILOT_UNHANDLED:
            return result
        from .spaces import spaces_action, UNHANDLED as SPACES_UNHANDLED
        result = spaces_action(self, action, data)
        if result is not SPACES_UNHANDLED:
            return result
        from .voice import voice_action, UNHANDLED as VOICE_UNHANDLED
        result = voice_action(self, action, data)
        if result is not VOICE_UNHANDLED:
            return result
        from .channels import channels_action, UNHANDLED as CHANNELS_UNHANDLED
        result = channels_action(self, action, data)
        if result is not CHANNELS_UNHANDLED:
            return result
        if action == 'plugins_list':return {'plugins':self.plugins.list(data.get('project_id'))}
        if action == 'choose_local_file':
            from .windows_ui import choose_file
            return {'path':choose_file()}
        from .model_preferences import handle
        model_result=handle(self,action,data)
        if model_result is not None:return model_result
        if action=='analytics':
            from .analytics import report
            return report(self,data['project_id'],data.get('conversation_id'))
        from .intelligence import settings_action
        handled = settings_action(self, action, data)
        if handled is not None: return handled
        if action == 'plugin_web_url':return self.plugins.web_url(data['id'])
        if action == 'plugin_create_project':
            with self.engine.lock:
                self._idle()
                return self.plugins.create_project(data)
        if action == 'mcp_local_register':
            from .mcp_registry import register
            with self.engine.lock:return register(self,data)
        if action == 'mcp_local_test':
            from .mcp_registry import test
            return test(self,data)
        if action == 'open_cymd':
            from .media import open_cymd
            return open_cymd(self,data)
        if action == 'cymd_open':
            project = self.project_for_conversation(data['conversation_id'])
            self.plugins.plugin('cymd', project['id'])
            if not data.get('id'):
                return {'name': 'Sans titre.md'}
            from .media import locate
            row, meta, path = locate(self.store, data['id'])
            if row['conversation_id'] != data['conversation_id']:
                raise ValueError('Pièce jointe hors conversation.')
            if path.stat().st_size > 50*1024*1024 or not row['name'].lower().endswith(('.cymd','.md','.markdown')):
                raise ValueError('Document incompatible ou supérieur à 50 Mo.')
            return {'name': row['name'], 'url': '/media/'+row['id']}
        if action == 'preview_cymd':
            from .media import document_preview
            return document_preview(self,data)
        if action == 'extension_state':return {'items':self.extensions.state()}
        if action == 'extension_check':return self.extensions.check(data.get('id'))
        if action == 'extension_install':return self.extensions.install(data['id'])
        if action == 'extension_open_download':return self.extensions.open_download(data['id'])
        if action == 'cytool_detect':
            from .cytool_discovery import discover
            return discover(data['folder'])
        if action == 'cytool_import':
            with self.engine.lock:
                self._idle()
                return self.plugins.import_cytool(data)
        if action == 'plugin_save':
            with self.engine.lock:
                self._idle()
                return self.plugins.save(data)
        if action == 'plugin_catalog':return self.plugins.catalog(data['id'])
        if action == 'plugin_bind':
            with self.engine.lock:
                self._idle()
                return self.plugins.bind(data)
        if action == 'plugin_read':return self.plugins.read(data['id'],data.get('project_id'),data.get('tool'),data.get('arguments'),data.get('resource'),discovery=True)
        if action == 'plugin_annotate':return self.plugins.annotate(data)
        if action == 'plugin_import_annotations':return self.plugins.import_annotations(data['conversation_id'])
        if action == 'plugin_attach':
            self.project_for_conversation(data['conversation_id'])
            project=self.store.one('SELECT project_id FROM conversations WHERE id=?',(data['conversation_id'],))['project_id']
            result=self.plugins.read(data['id'],project,data.get('tool'),data.get('arguments'),data.get('resource'))
            id=uid();self.store.execute('INSERT INTO files VALUES(?,?,?,?,?,?)',(id,data['conversation_id'],data['id']+' · référence MCP',json.dumps(result,ensure_ascii=False),'plugin',now()))
            return {'id':id}
        if action == 'update_project':
            project = self.store.one('SELECT * FROM projects WHERE id=?', (data['id'],))
            name = data.get('name', project['name']).strip()
            if not name:
                raise ValueError('Nom requis.')
            with self.engine.lock:
                self._idle()
                root = str(Path(data.get('root', project['root'])).resolve(strict=True))
                policy = PathPolicy([*self.engine.policy.roots, root], self.engine.policy.protected_roots)
                policy.project(root)
                self.config['allowed_roots'] = list(dict.fromkeys(str(r) for r in policy.roots))
                self.config_path.write_text(json.dumps(self.config, ensure_ascii=False, indent=2), encoding='utf-8')
                self.engine.policy = policy
                self.store.execute('UPDATE projects SET name=?,root=? WHERE id=?', (name[:120], root, project['id']))
                if root != project['root']:
                    self.store.execute('UPDATE sessions SET native_id=NULL,last_seq=0 WHERE conversation_id IN (SELECT id FROM conversations WHERE project_id=?)', (project['id'],))
            return {'ok': True}
        if action == 'approve_plan':
            source = self.store.one("SELECT * FROM missions WHERE id=? AND status='succeeded'", (data['id'],))
            spec = json.loads(source['spec'])
            proposal = spec.get('proposal', {}).get('plan')
            if not proposal or not data.get('acknowledged'):
                raise ValueError('Plan absent ou non autorisé.')
            current = self.conversation(source['conversation_id'])['plans']
            if not current or current[0]['id'] != source['id']:
                raise ValueError('Ce plan a été remplacé par une proposition plus récente.')
            if 'assignments' in data:
                from .planning import adjusted_plan
                proposal=adjusted_plan(proposal,data['assignments'],self.engine.connectors,self.catalogs)
            execution = {'conversation_id': source['conversation_id'], **proposal, 'request_key': 'plan:' + source['id'],
                         'message': 'Plan autorisé : ' + proposal['title'], 'timeout_seconds':int(data.get('timeout_seconds',0)), 'concurrency':int(data.get('concurrency',3))}
            with self.engine.lock:
                id = self.engine.create(execution)
                self.engine.launch(id)
            return {'mission_id': id}
        if action == 'set_storage':
            self.config.pop('storage_error', None)
            from .storage import validate_destination
            if data.get('cancel'):
                self.config.pop('pending_data_dir', None)
            else:
                destination = validate_destination(self.store.path.parent, data.get('path', ''))
                self.config['pending_data_dir'] = str(destination)
            self.config_path.write_text(json.dumps(self.config, ensure_ascii=False, indent=2), encoding='utf-8')
            return {'pending_data_dir': self.config.get('pending_data_dir', '')}
        if action == "choose_project_folder":
            from .windows_ui import choose_folder
            selected = choose_folder()
            if selected:
                root = PathPolicy([selected], self.engine.policy.protected_roots).project(selected)
                return {"root": root, "name": Path(root).name}
            return {"root": None}
        if action == "create_project":
            name = data.get("name", "").strip()
            if not name:
                raise ValueError("Nom du projet requis.")
            candidate = str(Path(data["root"]).resolve())
            with self.engine.lock:
                policy = PathPolicy([*self.engine.policy.roots, candidate], self.engine.policy.protected_roots)
                policy.project(candidate)
                self.config["allowed_roots"] = list(dict.fromkeys(str(r) for r in policy.roots))
                self.config_path.write_text(json.dumps(self.config, ensure_ascii=False, indent=2), encoding="utf-8")
                self.engine.policy = policy
            root = self.engine.policy.project(data["root"])
            name = data.get("name", "").strip()
            if not name:
                raise ValueError("Nom du projet requis.")
            appearance = {k: data[k] for k in ("color", "icon", "category") if data.get(k)}
            if appearance.get("category") and appearance["category"] not in self.config.get("categories", []):
                self.action("category", {"name": appearance["category"]})
            id = uid()
            self.store.execute("INSERT INTO projects(id,name,root,created_at) VALUES(?,?,?,?)", (id, name[:120], root, now()))
            if appearance:
                # Chosen in the creation dialog: same checks as when customising the project later.
                try:
                    self.action("organize", {"kind": "project", "id": id, **appearance})
                except ValueError:
                    self.store.execute("DELETE FROM projects WHERE id=?", (id,))
                    raise
            result = {"id": id}
            if data.get("assistant"):
                from .project_assistant import ensure
                result["assistant_conversation_id"] = ensure(self, id)["conversation_id"]
            return result
        if action == 'annotation_receive':
            from .annotation_delivery import receive
            return receive(self,data)
        if action == 'create_free_conversation':
            title=str(data.get('title','Discussion libre')).strip() or 'Discussion libre'
            # Native agents need a cwd. Each free chat gets an isolated workspace,
            # with no project memory or plugin binding inherited from another chat.
            project_id=self.free_workspace()
            result=self.action('create_conversation',{'project_id':project_id,'title':title,'mode':'chat'})
            return {**result,'project_id':project_id}
        if action == "create_conversation":
            project = self.store.one("SELECT * FROM projects WHERE id=?", (data["project_id"],))
            self.engine.policy.project(project["root"])
            id = uid()
            mode = data.get('mode', 'chat')
            if mode not in {'chat', 'orchestrator'}:
                raise ValueError('Type de conversation inconnu.')
            self.store.execute("INSERT INTO conversations(id,project_id,title,created_at,mode) VALUES(?,?,?,?,?)", (id, project["id"], data.get("title", "Nouvelle conversation")[:200], now(), mode))
            return {"id": id}
        if action in {"rename_conversation", "archive_conversation", "delete_conversation"}:
            self.project_for_conversation(data["id"])
            with self.engine.lock:
                self._idle(data["id"])
                if action == "delete_conversation":
                    self.store.execute("DELETE FROM conversations WHERE internal_parent_id=?",(data["id"],))
                    self.store.execute("DELETE FROM conversations WHERE id=?", (data["id"],))
                elif action == "rename_conversation":
                    if not data.get("title", "").strip():
                        raise ValueError("Titre requis.")
                    self.store.execute("UPDATE conversations SET title=? WHERE id=?", (data["title"][:200], data["id"]))
                else:
                    self.store.execute("UPDATE conversations SET archived=? WHERE id=?", (bool(data.get("archived", True)), data["id"]))
            return {"ok": True}
        if action == "branch":
            source = self.conversation(data["conversation_id"])
            anchor = self.store.one("SELECT * FROM messages WHERE id=? AND conversation_id=?", (data["message_id"], source["id"]))
            id = uid()
            with self.store.transaction() as db:
                db.execute("INSERT INTO conversations(id,project_id,title,archived,parent_id,branch_message_id,created_at,mode,workdirs) VALUES(?,?,?,?,?,?,?,?,?)", (id, source["project_id"], data.get("title") or source["title"] + " · branche", 0, source["id"], anchor["id"], now(), source['mode'],source['workdirs']))
                db.execute('UPDATE conversations SET agent_settings=? WHERE id=?',(source.get('agent_settings','{}'),id))
                for msg in source["messages"]:
                    if msg["seq"] <= anchor["seq"]:
                        self.store.message(id, msg["role"], msg["content"], msg["connector"], msg["model"], msg["id"], db=db, created_at=msg["created_at"])
                for file in self.store.rows("SELECT * FROM files WHERE conversation_id=? AND created_at<=?", (source["id"], anchor["created_at"])):
                    file_id=uid()
                    if file['kind']=='media':
                        from .media import locate,folder
                        import shutil
                        _,_,original=locate(self.store,file['id']);shutil.copy2(original,folder(self.store)/file_id)
                    db.execute("INSERT INTO files VALUES(?,?,?,?,?,?)", (file_id, id, file["name"], file["content"], file["kind"], file["created_at"]))
            return {"id": id, "notice": "Branche de messages créée ; aucun fichier restauré. Les sessions natives seront nouvelles."}
        if action == "context_preview":
            self.project_for_conversation(data["conversation_id"])
            return build_context(self.store, data["conversation_id"], data.get("instruction", ""), data.get("context", {}), self.engine.context_chars)
        if action in {'outbox_cancel','outbox_send_now','outbox_retry'}:
            from .conversation_queue import change
            return change(self,action,data)
        if action in {"create_mission", "continue_conversation"}:
            if action == 'continue_conversation' and not data.get('_from_outbox'):
                from .conversation_queue import busy, enqueue
                with self.engine.lock:
                    if busy(self,data['conversation_id']): return enqueue(self,data)
            if data.get("steps"):
                # A chain can call a specialist by profile: its connector, model and instructions are
                # resolved here, frozen at the revision used, and shown in the step like any other.
                from .teams import _loaded, current_definition
                resolved = []
                for step in data["steps"]:
                    if step.get("profile_id"):
                        profile = _loaded(self.store.one("SELECT * FROM agent_profiles WHERE id=?", (step["profile_id"],)))
                        if profile["archived"]:
                            raise ValueError("Profil archivé : " + profile["name"] + ". Réactivez-le ou choisissez un autre agent.")
                        definition = current_definition(profile)
                        step = {**step,
                                "name": step.get("name") or definition["name"],
                                "connector": definition["connector"], "model": step.get("model") or definition["model"],
                                "instruction": (definition["prompt"] + "\n\n" if definition["prompt"] else "") + step.get("instruction", ""),
                                **{k: v for k, v in definition.get("settings", {}).items() if k in {"effort", "service_tier"} and not step.get(k)}}
                    resolved.append(step)
                data = {**data, "steps": resolved}
            if action == "continue_conversation":
                conversation = self.conversation(data['conversation_id'])
                instruction = data['instruction']
                planning = conversation['mode'] == 'orchestrator' and not data.get('execution_only')
                if planning:
                    catalog = [{**c, 'models': self.catalogs.get(c['id'], []), 'default_model': c['model']} for c in self.state()['connectors'] if c['enabled']]
                    failures = self.store.rows('SELECT s.name,s.connector,s.model,s.status,s.error,s.result FROM steps s JOIN missions m ON m.id=s.mission_id WHERE m.conversation_id=? ORDER BY m.created_at DESC,s.position LIMIT 20', (conversation['id'],))
                    for step in failures:
                        if step['result']:
                            step['result'] = step['result'][:3000]
                    from .model_preferences import planning_preferences
                    instruction = planning_instruction(instruction, catalog, failures)+planning_preferences(self)
                data = {**data, 'planning': planning, 'message': data['instruction'], "title": data["instruction"][:80], "steps": [{"name": "Discussion orchestrateur" if planning else "Réponse", "connector": data["connector"], "model": data.get("model", ""), "instruction": instruction,"effort":data.get("effort",""),"service_tier":data.get("service_tier","")}]}
            with self.engine.lock:
                normal = action == 'continue_conversation' and not data.get('planning')
                if normal:
                    conversation = self.conversation(data['conversation_id'])
                id = self.engine.create(data)
                if normal:
                    self.store.execute('UPDATE conversations SET agent_id=?,agent_model=? WHERE id=?', (data['connector'], data.get('model',''), conversation['id']))
                if data.get("launch", True):
                    self.engine.launch(id)
            return {"mission_id": id}
        if action in {"launch_mission", "cancel_mission", "retry_mission", "pause_mission", "resume_mission"}:
            mission = self.store.one("SELECT * FROM missions WHERE id=?", (data["mission_id"],))
            self.project_for_conversation(mission["conversation_id"])
            if action == "launch_mission":
                self.engine.launch(mission["id"])
            elif action == "pause_mission":
                self.engine.pause(mission["id"])
            elif action == "resume_mission":
                self.engine.resume(mission["id"])
            elif action == "cancel_mission":
                self.engine.cancel(mission["id"])
            else:
                self.engine.retry(mission["id"], data.get("acknowledged", False), data.get("timeout_seconds"), data.get("concurrency"))
            return {"mission_id": mission["id"]}
        if action == "approve":
            self.engine.approve(data["id"], data["accepted"])
            return {"ok": True}
        if action in {"save_memory", "delete_memory"}:
            project = self.store.one("SELECT * FROM projects WHERE id=?", (data["project_id"],))
            self.engine.policy.project(project["root"])
            if action == "delete_memory":
                self.store.execute("DELETE FROM memory WHERE id=? AND project_id=?", (data["id"], project["id"]))
                return {"ok": True}
            content = data.get("content", "").strip()
            if not content or len(content) > 50000:
                raise ValueError("Mémoire vide ou trop longue.")
            sources = data.get("source_ids", [])
            for source in sources:
                self.store.one("SELECT m.id FROM messages m JOIN conversations c ON c.id=m.conversation_id WHERE m.id=? AND c.project_id=?", (source, project["id"]))
            id = data.get("id") or uid()
            existing = self.store.rows("SELECT * FROM memory WHERE id=?", (id,))
            if existing and existing[0]["project_id"] != project["id"]:
                raise ValueError("Mémoire hors projet.")
            self.store.execute("INSERT INTO memory(id,project_id,content,validated,source_ids,created_at,category) VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET content=excluded.content,validated=excluded.validated,source_ids=excluded.source_ids,category=excluded.category",
                               (id, project["id"], self.engine.secrets.redact(content), bool(data.get("validated", False)), json.dumps(sources), now(), str(data.get("category","Général"))[:80]))
            return {"id": id}
        if action == "attach_file":
            project = self.project_for_conversation(data["conversation_id"])
            path = scoped_workspace(project["root"], data["path"], json.loads(self.conversation(data["conversation_id"])["workdirs"]))
            if path.stat().st_size > 100000:
                raise ValueError("Pièce jointe limitée à 100 Ko de texte UTF-8.")
            content = self.engine.secrets.redact(path.read_text(encoding="utf-8"))
            id = uid()
            self.store.execute("INSERT INTO files VALUES(?,?,?,?,?,?)", (id, data["conversation_id"], str(path.relative_to(project["root"])), content, "attachment", now()))
            return {"id": id}
        if action == "delete_file":
            self.project_for_conversation(data["conversation_id"])
            row=self.store.one('SELECT * FROM files WHERE id=? AND conversation_id=?',(data['id'],data['conversation_id']))
            self.store.execute("DELETE FROM files WHERE id=? AND conversation_id=?", (data["id"], data["conversation_id"]))
            if row['kind']=='media':
                from .media import folder
                (folder(self.store)/row['id']).unlink(missing_ok=True)
            return {"ok": True}
        if action == "save_connector":
            connector = self.engine.connectors[data["id"]]
            if "native_auto_approve" in data and not isinstance(data["native_auto_approve"],bool):
                raise ValueError("Le réglage des outils automatiques doit être un booléen.")
            if "api_key" in data and data["id"] not in {"anthropic","openrouter"}:
                raise ValueError("Les agents utilisent leur propre authentification.")
            with self.engine.lock:
                self._idle()
                for key in ("model", "enabled", "executable", "native_auto_approve"):
                    if key in data:
                        connector.config[key] = data[key]
                self.config.setdefault("connectors", {})[data["id"]] = connector.config
                self.config_path.write_text(json.dumps(self.config, ensure_ascii=False, indent=2), encoding="utf-8")
                if "api_key" in data:
                    if data["id"] not in {"anthropic","openrouter"}:
                        raise ValueError("Les agents utilisent leur propre authentification.")
                    self.engine.secrets.set(data["id"], data["api_key"].strip())
                self.health.pop(data["id"], None)
            from .connector_health import start_probes
            start_probes(self, [data['id']])
            return {"ok": True}
        if action == "connect_claude":
            result = self.engine.connectors["claude-code"].login()
            self.health['claude-code'] = result if result.get('status') == 'connected' else {'status':'disconnected','detail':result['detail']}
            if result.get('status') != 'connected' and not getattr(self,'_claude_login_watching',False):
                import threading, time
                self._claude_login_watching = True
                def watch():
                    try:
                        for _ in range(60):
                            if self.engine.closing.wait(3): return
                            status = self.engine.connectors['claude-code'].auth_status()
                            if status['status'] == 'connected':
                                self.health['claude-code'] = status
                                return
                    finally: self._claude_login_watching = False
                threading.Thread(target=watch,daemon=True).start()
            return result
        if action == "test_connector":
            from .connector_health import probe
            return probe(self, data['id'])
        if action == "list_models":
            self.catalogs[data['id']] = self.engine.connectors[data["id"]].models()
            self.config['models_cache']=self.catalogs;self.plugins.persist()
            return {"models": self.catalogs[data['id']]}
        if action == "export":
            id = data["conversation_id"]
            conversation = self.conversation(id)
            conversation["missions"] = [self.mission(m["id"]) for m in self.store.rows("SELECT id FROM missions WHERE conversation_id=?", (id,))]
            for mission in conversation["missions"]:
                mission["events"] = self.store.rows("SELECT * FROM events WHERE mission_id=? ORDER BY seq", (mission["id"],))
                for event in mission["events"]:
                    event["data"] = json.loads(event["data"])
            conversation["files"] = self.store.rows("SELECT * FROM files WHERE conversation_id=?", (id,))
            return conversation
        if action == "backup":
            with self.engine.lock, self.store.transaction():
                return {"format": "cyai-backup", "version": 2, "created_at": now(), "categories":self.config.get("categories",[]), "tables": {t: self.store.rows(f"SELECT * FROM {t}") for t in TABLES + TEAM_TABLES}}
        if action == "restore":
            backup = data["backup"]
            tables = list(TABLES) if set(backup.get("tables", {})) == set(TABLES) else TABLES + TEAM_TABLES
            # Tables added after a version-2 backup was made are simply empty in it.
            later = {"project_spaces", "method_revisions", "method_assets", "profile_methods", "method_tests", "method_runs", "method_loops", "method_chains", "method_proposals", "member_assessments", "agent_benchmarks"}
            if backup.get("format") != "cyai-backup" or backup.get("version") not in {1, 2} or not set(tables) - later <= set(backup.get("tables", {})) <= set(tables):
                raise ValueError("Format de sauvegarde invalide.")
            categories=backup.get('categories',list(dict.fromkeys(p.get('category','') for p in backup['tables']['projects'] if p.get('category'))))
            if not isinstance(categories,list) or any(not isinstance(c,str) or len(c)>80 for c in categories):
                raise ValueError('Catégories de sauvegarde invalides.')
            for p in backup["tables"]["projects"]:
                self.engine.policy.project(p["root"])
            if not data.get("acknowledged"):
                raise ValueError("La restauration remplace l’historique local ; confirmation requise.")
            with self.engine.lock:
                self._idle()
                for conversation in backup['tables']['conversations']:
                    for directory in json.loads(conversation.get('workdirs','[]')):
                        self.engine.policy.project(directory)
                safety = self.action("backup", {})
                safety_path = self.store.path.parent / ("before-restore-" + uid() + ".json")
                safety_path.write_text(json.dumps(safety, ensure_ascii=False), encoding="utf-8")
                with self.store.transaction() as db:
                    for table in reversed(tables):
                        db.execute(f"DELETE FROM {table}")
                    for table in tables:
                        columns = [r[1] for r in db.execute(f"PRAGMA table_info({table})")]
                        for row in backup["tables"].get(table, []):
                            if table == 'conversations' and 'mode' not in row:
                                row = {**row, 'mode': 'chat'}
                            if table == 'conversations':
                                row = {'agent_id': None, 'agent_model': None, **row}
                            if table == 'projects':
                                row = {'free_chat':0,'archived':0,'favorite':0,'position':0,'color':'#b6a1f4','icon':'','category':'','agent_settings':'{}',**row}
                            if table == 'conversations':
                                row = {'favorite':0,'position':0,'workdirs':'[]','agent_settings':'{}','summary':'','summary_seq':0,**row}
                            if table == 'memory':
                                row = {'category':'Général','automatic':0,**row}
                            if set(row) != set(columns):
                                raise ValueError("Schéma de sauvegarde incompatible.")
                            db.execute(f"INSERT INTO {table}({','.join(columns)}) VALUES({','.join('?' for _ in columns)})", [row[c] for c in columns])
                    db.execute("UPDATE sessions SET native_id=NULL,last_seq=0")
                    db.execute("UPDATE missions SET status='interrupted' WHERE status IN ('queued','running','awaiting_approval','pausing')")
                    db.execute("UPDATE steps SET status='interrupted' WHERE status IN ('running','awaiting_approval')")
            return {"ok": True, "notice": "Historique restauré. Reprise par contexte ; sessions natives externes non incluses. Copie de sécurité conservée." +
                    ("" if TEAM_TABLES[0] in tables else " Sauvegarde antérieure aux équipes : la bibliothèque d’agents globale a été conservée telle quelle, les équipes des projets remplacés ont disparu avec eux.")}
        raise ValueError("Action inconnue.")
