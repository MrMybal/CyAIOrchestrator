"""Provider adapters. Only public protocols, no application subscription scraping."""
import asyncio
import base64
from collections import deque
import dataclasses
import importlib.util
import json
import os
import queue
import shutil
import signal
import socket
import subprocess
import threading
import time
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Protocol

from .security import scoped_path, scoped_workspace


class SessionBusy(RuntimeError):
    """Resume rejected before a turn started; safe to rebuild local context."""


class SessionUnavailable(SessionBusy):
    """Stored session cannot be restored; no provider turn has started."""


class Cancelled(Exception):
    pass


class Control:
    def __init__(self, timeout, approve, emit):
        self.cancelled = threading.Event()
        self.timeout_seconds = timeout
        self.deadline = time.monotonic() + timeout if timeout else None
        self.approve = approve
        self.emit = emit

    def check(self):
        if self.cancelled.is_set():
            raise Cancelled("Exécution annulée.")
        if self.deadline is not None and time.monotonic() > self.deadline:
            raise TimeoutError(f"Durée maximale de la mission dépassée ({self.timeout_seconds} secondes). CyAI a demandé l’arrêt du connecteur ; des effets peuvent déjà avoir été produits. Augmentez la durée lors de la reprise.")


class Connector(Protocol):
    id: str
    kind: str

    def check(self) -> dict: ...
    def models(self) -> list: ...
    def run(self, prompt: str, root: str, model: str, native_id: str | None, control: Control) -> str: ...


def executable(value):
    resolved = shutil.which(value)
    if not resolved:
        raise ValueError(f"Exécutable absent : {value}. Configurez son chemin dans config.json.")
    # npm shims on Windows: invoke node directly, never pass prompts through cmd.exe.
    p = Path(resolved)
    if p.suffix.lower() in {".cmd", ".ps1", ".bat"}:
        targets = {"claude": "@anthropic-ai/claude-code/cli.js", "opencode": "opencode-ai/bin/opencode", "codex": "@openai/codex/bin/codex.js"}
        script = p.parent / "node_modules" / targets.get(p.stem, "__missing__")
        if not script.is_file():
            package={"command-code":"command-code","cmdc":"command-code","codebuddy":"@tencent-ai/codebuddy-code","cbc":"@tencent-ai/codebuddy-code"}.get(p.stem)
            if package:
                base=(p.parent/"node_modules"/package).resolve()
                manifest=base/"package.json"
                if manifest.is_file():
                    bins=json.loads(manifest.read_text(encoding="utf-8")).get("bin",{})
                    target=bins if isinstance(bins,str) else bins.get(p.stem)
                    if target:
                        candidate=(base/target).resolve()
                        if candidate.is_relative_to(base):script=candidate
            if not script.is_file():
                raise ValueError("Shim Windows non reconnu ; configurez un exécutable natif.")
        return [shutil.which("node") or "node", str(script)]
    return [resolved]


def stop_process(proc):
    if proc.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"], capture_output=True,
                       creationflags=subprocess.CREATE_NO_WINDOW, timeout=10)
    else:
        os.killpg(proc.pid, signal.SIGTERM)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def spawn(args, root, env=None):
    process_env = os.environ.copy()
    # Nested orchestrators must not inherit the MCP bearer token or unrelated API keys.
    for name in list(process_env):
        if name.startswith("CYAI_") or name.endswith("_API_KEY"):
            process_env.pop(name, None)
    process_env.update(env or {})
    return subprocess.Popen(args, cwd=root, env=process_env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace", bufsize=1,
                            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                            start_new_session=os.name != "nt")


class JsonProcess:
    def __init__(self, args, root, control, env=None):
        self.proc = spawn(args, root, env)
        self.control = control
        self.inbox = queue.Queue()
        self.counter = 0
        self.pending = deque()
        self.errors = []
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._errors, daemon=True).start()

    def _errors(self):
        for line in self.proc.stderr:
            self.errors.append(line[:2000])
            self.errors = self.errors[-10:]

    def _read(self):
        for line in self.proc.stdout:
            try:
                self.inbox.put(json.loads(line))
            except ValueError:
                pass
        self.inbox.put(None)

    def send(self, value):
        self.proc.stdin.write(json.dumps(value) + "\n")
        self.proc.stdin.flush()

    def next(self):
        if self.pending:
            self.control.check()
            return self.pending.popleft()
        while True:
            self.control.check()
            try:
                value = self.inbox.get(timeout=.15)
                if value is None:
                    raise RuntimeError("Agent arrêté avant le résultat : " + "".join(self.errors)[-3000:])
                return value
            except queue.Empty:
                pass

    def request(self, method, params):
        self.counter += 1
        id = self.counter
        self.send({"id": id, "method": method, "params": params})
        notifications = []
        while True:
            value = self.next()
            if value.get("id") == id and "method" not in value:
                if "error" in value:
                    raise RuntimeError(json.dumps(value["error"], ensure_ascii=False))
                self.pending.extend(notifications)
                return value.get("result", {})
            # Initialization notifications are intentionally not persisted as user content.
            if "id" in value and "method" in value:
                self.send({"id": value["id"], "error": {"code": -32601, "message": "Unsupported during initialization"}})
            else:
                notifications.append(value)

    def close(self):
        stop_process(self.proc)
        for stream in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            stream.close()


class Base:
    kind = "agent"
    def __init__(self, id, config, secrets):
        self.id, self.config, self.secrets = id, config, secrets

    def check(self):
        try:
            executable(self.config.get("executable", self.id))
            return {"status": "installed", "detail": "Installé ; authentification à vérifier par une exécution.", "capabilities": ["sessions", "resume", "stream", "cancel", "approvals", "tools"]}
        except ValueError as e:
            return {"status": "unconfigured", "detail": str(e), "capabilities": []}

    def models(self):
        return []


def record_artifact(control, root, name):
    try:
        path = scoped_path(root, name)
        if path.is_file() and path.stat().st_size <= 100000:
            control.emit("artifact", {"path": str(path.relative_to(root)), "content": path.read_text(encoding="utf-8")})
    except (ValueError, OSError, UnicodeError):
        # Metadata remains in tool events when the file is deleted, binary or too large.
        pass


def mcp_elicitation_response(data, control):
    schema = data.get('requestedSchema', {})
    if data.get('mode') in {'form','openai/form','openaiForm'} and isinstance(schema,dict) and schema.get('type') == 'object' and not schema.get('properties') and not schema.get('required'):
        accepted = control.approve({'provider':'codex','method':'mcpServer/elicitation/request','request':data})
        return {'action':'accept','content':{}} if accepted else {'action':'decline'}
    control.emit('permission_denied', {'reason':'Cette demande MCP nécessite un formulaire ou une connexion externe non pris en charge. Aucune réponse n’a été inventée.', 'request':data})
    return {'action':'cancel'}


# Codex's elevated Windows sandbox (2026 releases, see openai/codex#46312) refuses a profile that forbids reading the
# disk outside the project, and the unelevated one cannot enforce that split at all. CyAI then lets Codex read the
# disk, keeps writing limited to the project, and forbids reading the places that hold secrets.
ROOT_READ_REQUIRED = 'requires effective `:root` read access'
SENSITIVE_HOME = ['.ssh', '.aws', '.azure', '.gnupg', '.kube', '.docker', '.claude', '.git-credentials', '.netrc', '.npmrc',
                  '.pypirc', '.codex/auth.json', '.codex/config.toml', '.codex/sessions', '.codex/archived_sessions',
                  '.codex/history.jsonl', '.codex/log']
SENSITIVE_APPDATA = ['GitHub CLI', 'Mozilla']
SENSITIVE_LOCALAPPDATA = ['Google/Chrome/User Data', 'Microsoft/Edge/User Data', 'BraveSoftware']
CYAI_DATA = ['cyai.sqlite3', 'cyai.sqlite3-wal', 'cyai.sqlite3-shm', 'secrets.dpapi', 'backups', 'window-state', 'voice-samples', 'media']


ACCESS_LEVELS = ('project', 'read', 'read_network', 'full')


def permission_summary(request):
    '''What a permission request from Codex asks for, in words.'''
    wanted = request.get('permissions') or {}
    files = wanted.get('fileSystem') or {}
    parts = []
    for entry in files.get('entries') or []:
        path = entry.get('path') or {}
        where = path.get('path') or path.get('pattern') or (path.get('value') or {}).get('kind', '')
        parts.append({'read': 'lecture', 'write': 'écriture', 'deny': 'interdiction'}.get(entry.get('access'), entry.get('access', '')) + ' : ' + str(where))
    parts += ['lecture : ' + p for p in files.get('read') or []] + ['écriture : ' + p for p in files.get('write') or []]
    if (wanted.get('network') or {}).get('enabled'):
        parts.append('accès à Internet')
    return ' · '.join(parts) or 'droits supplémentaires'


def widen_reads(filesystem, root, protected_roots):
    home = Path.home()
    places = [home / p for p in SENSITIVE_HOME]
    for variable, names in (('APPDATA', SENSITIVE_APPDATA), ('LOCALAPPDATA', SENSITIVE_LOCALAPPDATA)):
        if os.environ.get(variable):
            places += [Path(os.environ[variable]) / name for name in names]
    project = Path(root).resolve()
    for protected in protected_roots:
        protected = Path(protected)
        # A free discussion works inside CyAI's data folder: then only the data itself is closed, not its workspace.
        places += [protected / name for name in CYAI_DATA] if project.is_relative_to(protected.resolve()) else [protected]
    filesystem[':root'] = 'read'
    for place in places:
        filesystem.setdefault(str(place), 'deny')
    return [str(p) for p in places]


class Codex(Base):
    def configuration(self, root):
        config = {"features.multi_agent": False, "mcp_servers": {}}
        home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
        files = [home / "config.toml"] + [p / ".codex" / "config.toml" for p in [Path(root), *Path(root).parents]]
        for file in dict.fromkeys(files):
            if not file.is_file():
                continue
            data = tomllib.loads(file.read_text(encoding="utf-8"))
            if "sandbox_mode" in data:
                raise ValueError("Configuration Codex incompatible : sandbox_mode prend priorité sur les profils de permissions. Configurez un profil de permissions officiel avant d’utiliser ce connecteur.")
            for name in data.get("mcp_servers", {}):
                config["mcp_servers"][name] = {"enabled": False}
        return config

    def models(self):
        rpc = JsonProcess(executable(self.config.get("executable", "codex")) + ["app-server", "--listen", "stdio://"], str(Path.cwd()), Control(20, lambda data: False, lambda *args: None))
        try:
            rpc.request("initialize", {"clientInfo": {"name": "cyai_orchestrator", "version": "0.1.0"}, "capabilities": {}})
            rpc.send({"method": "initialized", "params": {}})
            result = rpc.request("model/list", {})
            return [{"id": m.get("model", m.get("id")), "name": m.get("displayName"), "description":m.get("description"), "efforts":m.get("supportedReasoningEfforts",[]), "default_effort":m.get("defaultReasoningEffort"), "service_tiers":m.get("serviceTiers",[]), "context_window":m.get("contextWindow",m.get("context_window")), "modalities":m.get("inputModalities",[]), "is_default":m.get("isDefault",False)} for m in result.get("data", [])]
        finally:
            rpc.close()

    def run(self, prompt, root, model, native_id, control):
        overrides = self.configuration(root)
        overrides['mcp_servers'].update({k:{**v,'enabled':True} for k,v in getattr(control,'mcp_servers',{}).items()})
        rpc = JsonProcess(executable(self.config.get("executable", "codex")) + ["app-server", "--listen", "stdio://"], root, control)
        thread_id = turn_id = None
        result = ""
        try:
            rpc.request("initialize", {"clientInfo": {"name": "cyai_orchestrator", "version": "0.1.0"}, "capabilities": {}})
            rpc.send({"method": "initialized", "params": {}})
            params = {"cwd": root, "approvalPolicy": "on-request", "approvalsReviewer": "user", "config": {
                **overrides,
                "default_permissions": "cyai-project",
                "permissions.cyai-project": {"extends": ":workspace", "filesystem": {
                    ":root": "deny", ":minimal": "read", ":tmpdir": "deny", ":slash_tmp": "deny",
                    ":workspace_roots": {".": "read" if getattr(control, 'planning', False) else "write", ".data": "deny", ".env": "deny", ".codex": "read", ".git": "read"}},
                    "network": {"enabled": False}}}}
            # The access chosen in CyAI for this conversation (or by default): the project only, the disk read,
            # plus Internet, or everything. Secrets and CyAI's own data stay closed below « complet ».
            access = getattr(control, 'access', 'project') if getattr(control, 'access', 'project') in ACCESS_LEVELS else 'project'
            if access != 'project' and not getattr(control, 'planning', False):
                profile = params['config']['permissions.cyai-project']
                closed = widen_reads(profile['filesystem'], root, getattr(control, 'protected_roots', []))
                if access in ('read_network', 'full'):
                    profile['network'] = {'enabled': True}
                control.emit('sandbox_access', {'level': access, 'detail': {
                    'read': 'Codex peut lire le disque, sauf les dossiers qui contiennent des secrets ; il écrit seulement dans le projet.',
                    'read_network': 'Codex peut lire le disque (secrets exclus) et utiliser Internet ; il écrit seulement dans le projet.',
                    'full': 'Accès complet : Codex travaille sans bac à sable. Il peut lire et écrire partout, y compris dans '
                            'les données de CyAI, et utiliser Internet.'}[access]})
            for directory in getattr(control, 'workdirs', []):
                fs = params['config']['permissions.cyai-project']['filesystem']
                fs[directory] = 'read' if getattr(control,'planning',False) else 'write'
                for metadata in ('.git','.codex'):
                    fs[str(Path(directory)/metadata)] = 'read'
                for protected in ('.data','.env','.ssh','.aws','.claude','secrets.dpapi'):
                    fs[str(Path(directory)/protected)] = 'deny'
            if access == 'full' and not getattr(control, 'planning', False):
                # The elevated Windows sandbox cannot grant writing to the whole disk: full access is Codex's own mode
                # without a sandbox, chosen explicitly by you for this conversation.
                params['config'].pop('default_permissions', None)
                params['config'].pop('permissions.cyai-project', None)
                params['sandbox'] = 'danger-full-access'
            if model:
                params["model"] = model
            if native_id:
                params["threadId"] = native_id

            def open_thread(method):
                try:
                    return rpc.request(method, params)
                except RuntimeError as refused:
                    if ROOT_READ_REQUIRED not in str(refused) or 'permissions.cyai-project' not in params['config'] \
                            or params['config']['permissions.cyai-project']['filesystem'].get(':root') == 'read':
                        raise
                    closed = widen_reads(params['config']['permissions.cyai-project']['filesystem'], root, getattr(control, 'protected_roots', []))
                    control.emit('sandbox_adjusted', {'detail': 'Le bac à sable Windows élevé de Codex exige la lecture du disque : '
                                                                'Codex peut lire hors du projet, sauf les dossiers qui contiennent des secrets '
                                                                '(clés, jetons, profils de navigateur, données CyAI). L’écriture reste limitée au projet.',
                                                      'denied': closed})
                    return rpc.request(method, params)
            try:
                try:
                    thread = open_thread("thread/resume" if native_id else "thread/start")
                except RuntimeError as archived:
                    if not native_id or 'is archived' not in str(archived).lower():
                        raise
                    # Resuming this CyAI conversation explicitly requests this same session.
                    try:
                        rpc.request('thread/unarchive', {'threadId':native_id})
                    except RuntimeError as restore_error:
                        raise SessionUnavailable(str(restore_error)) from restore_error
                    control.emit('session_unarchived', {'native_id':native_id, 'detail':'Session Codex désarchivée pour reprendre cette conversation.'})
                    thread = open_thread('thread/resume')
            except RuntimeError as exc:
                if isinstance(exc,SessionUnavailable):raise
                if native_id and any(marker in str(exc).lower() for marker in ('thread not found','session not found','no rollout found')):
                    raise SessionUnavailable(str(exc)) from exc
                if native_id and 'already has an active writer' in str(exc):
                    raise SessionBusy(str(exc)) from exc
                raise
            thread_id = thread["thread"]["id"]
            control.emit("session", {"native_id": thread_id})
            if getattr(control,'conversation_title',''):
                rpc.request('thread/name/set', {'threadId':thread_id,'name':control.conversation_title})
            if thread.get("model"):
                control.emit("model", {"model": thread["model"], "provider": thread.get("modelProvider")})
            if getattr(control,'effort','') or getattr(control,'service_tier',''):
                available=rpc.request('model/list',{}).get('data',[])
                selected=next((m for m in available if m.get('model',m.get('id'))==(thread.get('model') or model)),None)
                if selected is None: selected=next((m for m in available if m.get('isDefault')),None)
                if not selected: raise ValueError('Impossible de vérifier les réglages de ce modèle.')
                if getattr(control,'effort','') and control.effort not in [v['reasoningEffort'] for v in selected.get('supportedReasoningEfforts',[])]:raise ValueError('Niveau d’effort non annoncé pour ce modèle.')
                if getattr(control,'service_tier','') and control.service_tier not in ['default',*[v['id'] for v in selected.get('serviceTiers',[])]]:raise ValueError('Vitesse non annoncée pour ce modèle.')
            turn_params={"threadId":thread_id,"input":[{"type":"text","text":prompt}],"cwd":root,"approvalPolicy":"on-request","approvalsReviewer":"user"}
            if getattr(control,'effort',''):turn_params['effort']=control.effort
            if getattr(control,'service_tier',''):turn_params['serviceTier']=control.service_tier
            turn_params['input'].extend({'type':'image','url':'data:'+im['mime']+';base64,'+im['data']} for im in getattr(control,'images',[]))
            turn = rpc.request("turn/start", turn_params)
            turn_id = turn["turn"]["id"]
            while True:
                event = rpc.next()
                method, data = event.get("method", ""), event.get("params", {})
                if "id" in event and method:
                    if method in {"item/commandExecution/requestApproval", "item/fileChange/requestApproval"}:
                        accepted = control.approve({"provider": "codex", "method": method, "request": data})
                        rpc.send({"id": event["id"], "result": {"decision": "accept" if accepted else "decline"}})
                    elif method == "mcpServer/elicitation/request":
                        rpc.send({'id':event['id'],'result':mcp_elicitation_response(data,control)})
                    elif method == "item/permissions/requestApproval":
                        # Never broadened silently: you decide, and a yes holds for this conversation's session.
                        accepted = control.approve({"provider": "codex", "method": method, "request": data, "summary": permission_summary(data)})
                        if not accepted:
                            control.emit("permission_denied", {"reason": "Droits supplémentaires refusés.", "request": data})
                        rpc.send({"id": event["id"], "result": {"permissions": (data.get("permissions") or {}) if accepted else {}, "scope": "session"}})
                    else:
                        control.emit("unsupported_request", {"method": method, "request": data})
                        rpc.send({"id": event["id"], "error": {"code": -32601, "message": "Request not supported by CyAI"}})
                elif method in {"item/reasoning/summaryTextDelta", "item/reasoning/textDelta"}:
                    control.emit('thinking', {'text':data.get('delta','')})
                elif method == 'item/started':
                    item=data.get('item',{})
                    if item.get('type')=='agentMessage' and result:
                        control.emit('delta',{'text':'\n\n'})
                    control.emit('activity',{'type':item.get('type',''), 'name':item.get('name') or item.get('command') or item.get('type','')})
                elif method == "item/agentMessage/delta":
                    control.emit("delta", {"text": data.get("delta", "")})
                elif method == "item/completed":
                    item = data.get("item", {})
                    if item.get("type") == "agentMessage":
                        result += item.get("text", "") + "\n\n"
                    elif item.get("type") in {"commandExecution", "fileChange", "mcpToolCall", "dynamicToolCall", "webSearch", "imageGeneration"}:
                        control.emit("tool", item)
                        if item.get("type") == "fileChange":
                            for change in item.get("changes", []):
                                if change.get("path"):
                                    record_artifact(control, root, change["path"])
                elif method == "thread/tokenUsage/updated":
                    control.emit("usage", data.get("tokenUsage", {}))
                elif method == "turn/completed":
                    turn = data.get("turn", {})
                    if turn.get("status") != "completed":
                        raise RuntimeError(json.dumps(turn.get("error") or {"status": turn.get("status")}))
                    return result.strip()
                elif method == "error":
                    control.emit("provider_error", data)
        finally:
            if thread_id and turn_id:
                try:
                    rpc.send({"id": 999999, "method": "turn/interrupt", "params": {"threadId": thread_id, "turnId": turn_id}})
                except (OSError, ValueError):
                    pass
            rpc.close()


class ClaudeCode(Base):
    def models(self):
        from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
        async def discover():
            async with ClaudeSDKClient(options=ClaudeAgentOptions(cli_path=self.auth_cli(), tools=[], setting_sources=[], strict_mcp_config=True)) as client:
                info=await client.get_server_info()
                models=(info or {}).get('models',[])
                if not models:
                    raise ValueError('Le CLI Claude ne fournit aucun modèle. Vérifiez sa connexion et réessayez.')
                return [{'id':m.get('value') or m.get('id'), 'name':m.get('displayName') or m.get('name') or m.get('value'), 'description':m.get('description',''), 'efforts':[{'reasoningEffort':v} for v in m.get('supportedEffortLevels',[])]} for m in models if m.get('value') or m.get('id')]
        async def bounded():
            return await asyncio.wait_for(discover(),timeout=25)
        try:return asyncio.run(bounded())
        except asyncio.TimeoutError:raise ValueError('Le catalogue Claude ne répond pas après 25 secondes. Réessayez depuis les connecteurs.')

    def auth_cli(self):
        configured = self.config.get('executable')
        candidates = [configured, shutil.which('claude.exe'), str(Path.home()/'.local/bin/claude.exe')]
        for candidate in candidates:
            if candidate and Path(candidate).is_file() and Path(candidate).suffix.lower() == '.exe':
                return str(Path(candidate).resolve())
        if configured:
            raise ValueError('Sélectionnez un CLI Claude natif .exe. Les anciens scripts npm ne sont pas compatibles avec le SDK actuel.')
        import claude_agent_sdk
        path = Path(claude_agent_sdk.__file__).parent / "_bundled" / ("claude.exe" if os.name == "nt" else "claude")
        if not path.is_file():
            raise ValueError("Le CLI Claude est absent. Téléchargez-le depuis Paramètres > Téléchargements, ou installez le CLI natif officiel.")
        return str(path)

    def auth_status(self):
        cli = self.auth_cli()
        try:
            result = subprocess.run([cli, "auth", "status"], capture_output=True,
                text=True, encoding="utf-8", errors="replace", timeout=12,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        except subprocess.TimeoutExpired:
            return {'status':'error','cli_path':cli,'detail':'Le CLI Claude ne répond pas après 12 secondes. Fermez une connexion CLI bloquée puis cliquez sur Tester.'}
        try:
            connected = json.loads(result.stdout).get("loggedIn") is True and result.returncode == 0
        except (ValueError, AttributeError):
            connected = False
        return {"status": "connected" if connected else "disconnected",
                "cli_path": cli, "detail": "Compte Claude Code connecté. Vous pouvez lancer une conversation." if connected else "Le CLI Claude Code n’est pas connecté. Cliquez sur « Se connecter au compte Claude ». La connexion de Claude Desktop ne peut pas être reprise par le CLI."}

    def login(self):
        status = self.auth_status()
        if status['status'] == 'connected':
            return {**status, 'detail': 'Connexion locale existante réutilisée. Vous pouvez discuter avec Claude Code.'}
        previous = getattr(self, "_login_process", None)
        if previous is None or previous.poll() is not None:
            self._login_process = subprocess.Popen([self.auth_cli(), "auth", "login"],
                creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0)
        return {"detail": "La connexion officielle Claude Code est ouverte dans un terminal. Terminez l’identification dans la page proposée par Claude, puis cliquez sur Vérifier la connexion. CyAI réutilisera ensuite cette connexion locale."}

    def check(self):
        if importlib.util.find_spec("claude_agent_sdk") is None:
            return {"status": "unconfigured", "detail": "Installer : python -m pip install claude-agent-sdk", "capabilities": []}
        return {"status": "installed", "detail": "SDK présent ; connexion Claude Code à vérifier.", "capabilities": ["sessions", "resume", "stream", "cancel", "approvals", "file_tools"]}

    def run(self, prompt, root, model, native_id, control):
        from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions, PermissionResultAllow, PermissionResultDeny, HookMatcher

        async def run():
            async def result_hook(data, tool_use_id, context):
                control.emit("tool_result", {"tool": data.get("tool_name"), "result": data.get("tool_response")})
                if data.get("tool_name") in {"Write", "Edit"}:
                    path = data.get("tool_input", {}).get("file_path")
                    if path:
                        record_artifact(control, root, path)
                return {}
            async def scope_hook(data, tool_use_id, context):
                if data.get('tool_name','').startswith('mcp__cyai_plugins__'):
                    return {}
                try:
                    inputs = data.get("tool_input", {})
                    if data.get("tool_name") == "Glob":
                        pattern = inputs.get("pattern", "")
                        if Path(pattern).is_absolute() or ".." in Path(pattern).parts:
                            raise ValueError("Motif de recherche hors projet.")
                    scoped_workspace(root, inputs.get("file_path") or inputs.get("path") or ".", getattr(control,"workdirs",()), must_exist=data.get("tool_name") != "Write")
                    return {}
                except (ValueError, OSError) as e:
                    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": str(e)}}
            async def permission(tool, data, context):
                try:
                    if tool in {'mcp__cyai_plugins__list_plugins','mcp__cyai_plugins__read_plugin','mcp__cyai_plugins__cyai_actions','mcp__cyai_plugins__cyai_call'}:
                        return PermissionResultAllow(updated_input=data)
                    if tool not in {"Read", "Write", "Edit", "Glob", "Grep"}:
                        return PermissionResultDeny(message="Outil non autorisé par CyAI. Les commandes shell nécessitent le connecteur Codex.")
                    scoped_workspace(root, data.get("file_path") or data.get("path") or ".", getattr(control,"workdirs",()), must_exist=tool != "Write")
                    accepted = await asyncio.to_thread(control.approve, {"provider": "claude-code", "tool": tool, "input": data})
                    return PermissionResultAllow(updated_input=data) if accepted else PermissionResultDeny(message="Refus utilisateur")
                except ValueError as e:
                    return PermissionResultDeny(message=str(e))
            options = ClaudeAgentOptions(effort=getattr(control,'effort',None) or None, cwd=root, add_dirs=getattr(control,"workdirs",[]), cli_path=self.auth_cli(), resume=native_id, model=model or None, permission_mode="default",
                                         tools=["Read", "Glob", "Grep"] if getattr(control, 'planning', False) else ["Read", "Write", "Edit", "Glob", "Grep"], can_use_tool=permission,
                                         setting_sources=[], mcp_servers=getattr(control,'mcp_servers',{}), strict_mcp_config=True, include_partial_messages=True,
                                         hooks={"PreToolUse": [HookMatcher(hooks=[scope_hook])], "PostToolUse": [HookMatcher(hooks=[result_hook])]}, stderr=lambda line: None)
            result = ""
            async with ClaudeSDKClient(options=options) as client:
                if getattr(control,'images',[]):
                    async def image_prompt():
                        yield {'type':'user','message':{'role':'user','content':[{'type':'text','text':prompt}]+[{'type':'image','source':{'type':'base64','media_type':im['mime'],'data':im['data']}} for im in control.images]}}
                    await client.query(image_prompt())
                else:await client.query(prompt)
                iterator = client.receive_response().__aiter__()
                while True:
                    pending = asyncio.create_task(iterator.__anext__())
                    try:
                        while not pending.done():
                            await asyncio.sleep(.1)
                            try:
                                control.check()
                            except (Cancelled, TimeoutError):
                                await client.interrupt()
                                pending.cancel()
                                raise
                        msg = pending.result()
                    except StopAsyncIteration:
                        break
                    value = dataclasses.asdict(msg) if dataclasses.is_dataclass(msg) else {}
                    type_name = type(msg).__name__
                    if value.get("session_id"):
                        control.emit("session", {"native_id": value["session_id"]})
                    if type_name == "SystemMessage" and value.get("data", {}).get("session_id"):
                        control.emit("session", {"native_id": value["data"]["session_id"]})
                    if type_name == "StreamEvent":
                        delta = value.get("event", {}).get("delta", {})
                        if delta.get('type') == 'thinking_delta':
                            control.emit('thinking', {'text':delta.get('thinking','')})
                        if delta.get("type") == "text_delta":
                            control.emit("delta", {"text": delta.get("text", "")})
                    if type_name == "AssistantMessage":
                        if value.get("model"):
                            control.emit("model", {"model": value["model"], "provider": "anthropic"})
                        for block in value.get("content", []):
                            if "text" in block:
                                result += block["text"] + "\n"
                            elif "name" in block:
                                control.emit("tool", block)
                    if type_name == "ResultMessage":
                        control.emit("usage", {"tokens": value.get("usage"), "cost_usd": value.get("total_cost_usd")})
                        if value.get("is_error"):
                            raise RuntimeError(value.get("result") or str(value.get("subtype")))
                        if getattr(control,'conversation_title','') and value.get('session_id'):
                            from claude_agent_sdk import rename_session
                            try: rename_session(value['session_id'], control.conversation_title, directory=root)
                            except (OSError, ValueError) as exc: control.emit('warning', {'message':'Synchronisation du titre Claude impossible : '+str(exc)})
                        return value.get("result") or result.strip()
            raise RuntimeError("Flux Claude Code terminé sans résultat final.")
        return asyncio.run(run())


def request_json(url, body=None, headers=None, method=None, timeout=20):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **(headers or {})}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        data = response.read()
        return json.loads(data) if data else {}


class OpenCode(Base):
    def models(self):
        output = subprocess.run(executable(self.config.get("executable", "opencode")) + ["models"], capture_output=True, text=True,
                                timeout=20, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        if output.returncode:
            raise ValueError("OpenCode ne peut pas lister les modèles.")
        return [{"id": s.strip()} for s in output.stdout.splitlines() if "/" in s]

    def run(self, prompt, root, model, native_id, control):
        import secrets
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        password = secrets.token_urlsafe(32)
        headers = {"Authorization": "Basic " + base64.b64encode(("opencode:" + password).encode()).decode()}
        permission = {"*": "deny", "read": "ask", "edit": "ask", "glob": "ask", "grep": "ask", "external_directory": "deny", "doom_loop": "deny"}
        mcp={name:{'type':'local','command':[cfg['command'],*cfg.get('args',[])],'environment':cfg.get('env',{}),'enabled':True,'timeout':600000} for name,cfg in getattr(control,'mcp_servers',{}).items()}
        permission['cyai_plugins_*']='allow'
        proc = spawn(executable(self.config.get("executable", "opencode")) + ["serve", "--hostname", "127.0.0.1", "--port", str(port)], root,
                     {"OPENCODE_SERVER_PASSWORD": password, "OPENCODE_CONFIG_CONTENT": json.dumps({"permission": permission, "mcp": mcp})})
        threading.Thread(target=lambda: deque(proc.stdout, maxlen=0), daemon=True).start()
        threading.Thread(target=lambda: deque(proc.stderr, maxlen=0), daemon=True).start()
        base = f"http://127.0.0.1:{port}"
        session_id = None
        try:
            for _ in range(100):
                control.check()
                try:
                    request_json(base + "/global/health", headers=headers, timeout=1)
                    break
                except (OSError, ValueError):
                    time.sleep(.1)
            else:
                raise RuntimeError("OpenCode ne démarre pas.")
            session_id = native_id or request_json(base + "/session", {"title": getattr(control,"conversation_title","CyAI Orchestrator")}, headers)["id"]
            control.emit("session", {"native_id": session_id})
            if getattr(control,'conversation_title',''):
                request_json(base + f"/session/{session_id}", {'title':control.conversation_title}, headers, method='PATCH')
            previous = request_json(base + f"/session/{session_id}/message", headers=headers)
            seen = {m["info"]["id"] for m in previous}
            body = {"parts": [{"type": "text", "text": prompt}]}
            body['parts'].extend({'type':'file','mime':im['mime'],'url':'data:'+im['mime']+';base64,'+im['data']} for im in getattr(control,'images',[]))
            if model:
                provider, model_id = model.split("/", 1)
                body["model"] = {"providerID": provider, "modelID": model_id}
            request_json(base + f"/session/{session_id}/prompt_async", body, headers)
            # Poll persisted messages as well as permissions; reconnection cannot lose a delta.
            lengths = {}
            handled = set()
            while True:
                control.check()
                try:
                    pending = request_json(base + "/permission", headers=headers)
                except urllib.error.HTTPError as e:
                    raise RuntimeError("Version OpenCode incompatible : endpoint /permission absent.") from e
                for item in pending:
                    if item.get("sessionID") == session_id and item["id"] not in handled:
                        accept = control.approve({"provider": "opencode", "request": item})
                        request_json(base + f"/permission/{item['id']}/reply", {"reply": "once" if accept else "reject"}, headers)
                        handled.add(item["id"])
                messages = request_json(base + f"/session/{session_id}/message", headers=headers)
                replies = [m for m in messages if m["info"]["id"] not in seen and m["info"].get("role") == "assistant"]
                for message in replies:
                    if message["info"].get("error"):
                        raise RuntimeError(json.dumps(message["info"]["error"]))
                    for part in message.get("parts", []):
                        if part.get("type") == "text":
                            text = part.get("text", "")
                            start = lengths.get(part["id"], 0)
                            if len(text) > start:
                                control.emit("delta", {"text": text[start:]})
                                lengths[part["id"]] = len(text)
                        elif part.get("type") == "tool" and part.get("state", {}).get("status") in {"completed", "error"} and part["id"] not in handled:
                            control.emit("tool", part)
                            if part.get("tool") in {"write", "edit"} and part["state"]["status"] == "completed":
                                path = part["state"].get("input", {}).get("filePath")
                                if path:
                                    record_artifact(control, root, path)
                            handled.add(part["id"])
                if replies and replies[-1]["info"].get("finish") not in {None, "tool-calls", "unknown"}:
                    info = replies[-1]["info"]
                    control.emit("usage", {"tokens": info.get("tokens"), "cost_usd": info.get("cost")})
                    return "\n".join(p.get("text", "") for m in replies for p in m.get("parts", []) if p.get("type") == "text")
                time.sleep(.25)
        finally:
            if session_id:
                try:
                    request_json(base + f"/session/{session_id}/abort", {}, headers, timeout=2)
                except OSError:
                    pass
            stop_process(proc)


class Anthropic(Base):
    kind = "model"
    def headers(self):
        key = self.secrets.get("anthropic")
        if not key:
            raise ValueError("Configurez une clé API Anthropic dans les connecteurs.")
        return {"x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}

    def check(self):
        configured = bool(self.secrets.get("anthropic"))
        return {"status": "configured" if configured else "unconfigured", "detail": "Clé présente, à tester." if configured else "Clé API Anthropic requise ; indépendante de l’abonnement Claude.",
                "capabilities": ["stream", "cancel", "models", "app_file_tools", "approvals"], "native_resume": False}

    def models(self):
        result = request_json("https://api.anthropic.com/v1/models?limit=100", headers=self.headers())
        return [{"id": m["id"], "name": m.get("display_name")} for m in result["data"]]

    def run(self, prompt, root, model, native_id, control):
        if not model:
            raise ValueError("Choisissez un identifiant de modèle Anthropic dans la configuration.")
        messages = [{"role": "user", "content": [{'type':'text','text':prompt}]+[{'type':'image','source':{'type':'base64','media_type':im['mime'],'data':im['data']}} for im in getattr(control,'images',[])]}]
        tools = [{"name": "read_file", "description": "Read a UTF-8 file inside the authorized project.", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
                 {"name": "write_file", "description": "Write a UTF-8 file after explicit user approval.", "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}]
        if hasattr(control,'plugin_call'):
            from .app_mcp import TOOLS as APP_TOOLS
            tools += [{'name':t['name'],'description':t['description'],'input_schema':t['inputSchema']} for t in APP_TOOLS]
            tools += [{'name':'cyai_list_plugins','description':'Discover project reference plugins when the user asks to consult methods or resources.','input_schema':{'type':'object','properties':{}}},
                      {'name':'cyai_read_plugin','description':'Read reference data from a project-scoped plugin.','input_schema':{'type':'object','properties':{'plugin':{'type':'string'},'tool':{'type':'string'},'arguments':{'type':'object'},'resource':{'type':'string'}},'required':['plugin']}}]
        if getattr(control,'benchmark',False): tools=[]
        partial_output = []
        while True:
            control.check()
            req = urllib.request.Request("https://api.anthropic.com/v1/messages", headers=self.headers(),
                                         data=json.dumps({"model": model, "max_tokens": 4096, "stream": True, "messages": messages, "tools": tools}).encode())
            blocks, usage, stopped, stop_reason = {}, {}, False, None
            with urllib.request.urlopen(req, timeout=20) as response:
                for line in response:
                    control.check()
                    if not line.startswith(b"data: "):
                        continue
                    event = json.loads(line[6:])
                    kind = event.get("type")
                    if kind == "error":
                        raise RuntimeError(json.dumps(event.get("error")))
                    if kind == "message_start":
                        usage.update(event["message"].get("usage", {}))
                    if kind == "content_block_start":
                        blocks[event["index"]] = event["content_block"] | {"_json": ""}
                    if kind == "content_block_delta":
                        block, delta = blocks[event["index"]], event["delta"]
                        if delta["type"] == "text_delta":
                            block["text"] = block.get("text", "") + delta["text"]
                            control.emit("delta", {"text": delta["text"]})
                        elif delta["type"] == "input_json_delta":
                            block["_json"] += delta["partial_json"]
                    if kind == "message_delta":
                        usage.update(event.get("usage", {}))
                        stop_reason = event.get("delta", {}).get("stop_reason")
                    if kind == "message_stop":
                        stopped = True
            if not stopped:
                raise RuntimeError("Flux API interrompu avant confirmation finale.")
            control.emit("usage", usage)
            content = []
            for block in blocks.values():
                raw = block.pop("_json")
                if block["type"] == "tool_use" and raw:
                    if stop_reason == 'max_tokens':
                        raise RuntimeError("Le fournisseur a tronqué un appel d’outil : aucun appel partiel exécuté. La réponse est conservée ; reprenez en demandant de fractionner l’action.")
                    block["input"] = json.loads(raw)
                content.append(block)
            if stop_reason == "max_tokens":
                if any(b['type']=='tool_use' for b in content):
                    raise RuntimeError("Le fournisseur a tronqué un appel d’outil : aucun appel partiel exécuté. La réponse est conservée ; reprenez en demandant de fractionner l’action.")
                chunk="\n".join(b.get('text','') for b in content if b['type']=='text')
                if not chunk:raise RuntimeError("Le fournisseur a atteint sa limite de sortie sans contenu exploitable. Changez de modèle ou réduisez le contexte avant de reprendre.")
                partial_output.append(chunk)
                messages.append({'role':'assistant','content':content})
                messages.append({'role':'user','content':'Continue exactement où la réponse a été interrompue, sans répéter les parties précédentes.'})
                control.emit('activity',{'detail':'Réponse partielle conservée ; poursuite de la génération.'})
                continue
            calls = [b for b in content if b["type"] == "tool_use"]
            if calls and getattr(control,'benchmark',False): raise ValueError('Le candidat a demandé un outil dans un exercice sans outils.')
            if not calls:
                return "\n".join(partial_output + [b.get("text", "") for b in content if b["type"] == "text"])
            messages.append({"role": "assistant", "content": content})
            results = []
            for call in calls:
                control.check()
                error = False
                try:
                    data = call["input"]
                    if call['name'] in {'cyai_list_plugins','cyai_read_plugin','cyai_actions','cyai_call'} and hasattr(control,'plugin_call'):
                        output=json.dumps(control.plugin_call(call['name'] if call['name'] in {'cyai_actions','cyai_call'} else call['name'].removeprefix('cyai_'),data),ensure_ascii=False)
                        control.emit('tool_result',{'tool':call['name'],'result':output})
                        results.append({'type':'tool_result','tool_use_id':call['id'],'content':output})
                        continue
                    path = scoped_workspace(root, data["path"], getattr(control,"workdirs",()), must_exist=call["name"] != "write_file")
                    control.emit("tool", call)
                    if call["name"] == "read_file":
                        if path.stat().st_size > 100000:
                            raise ValueError("Fichier trop volumineux (100 Ko maximum).")
                        output = path.read_text(encoding="utf-8")
                    elif call["name"] == "write_file":
                        if not control.approve({"provider": "anthropic", "tool": "write_file", "path": str(path), "content": data["content"]}):
                            raise ValueError("Écriture refusée.")
                        control.check()
                        path = scoped_workspace(root, data["path"], getattr(control,"workdirs",()), must_exist=False)
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(data["content"], encoding="utf-8")
                        output = "Fichier écrit."
                        control.emit("artifact", {"path": data["path"], "content": data["content"]})
                    else:
                        raise ValueError("Outil inconnu.")
                except (ValueError, OSError) as e:
                    output, error = str(e), True
                control.emit("tool_result", {"id": call["id"], "output": output, "is_error": error})
                results.append({"type": "tool_result", "tool_use_id": call["id"], "content": output, "is_error": error})
            messages.append({"role": "user", "content": results})


class Ollama(Base):
    kind = "model"
    def base(self):
        base = self.config.get("base_url", "http://127.0.0.1:11434").rstrip("/")
        parsed = urllib.parse.urlparse(base)
        if parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.scheme != "http":
            raise ValueError("Ollama doit utiliser une adresse HTTP de boucle locale.")
        return base

    def check(self):
        return {"status": "configured", "detail": "Endpoint local configuré ; disponibilité à tester.", "capabilities": ["models", "stream", "cancel"], "native_resume": False}

    def models(self):
        return [{"id": m["name"]} for m in request_json(self.base() + "/api/tags")["models"]]

    def run(self, prompt, root, model, native_id, control):
        if not model:
            raise ValueError("Choisissez un modèle installé dans Ollama.")
        if hasattr(control,'plugin_call'):
            from .local_tools import run
            return run(self.base()+'/api/chat',{'Content-Type':'application/json'},prompt,control,model,ollama=True)
        req = urllib.request.Request(self.base() + "/api/chat", headers={"Content-Type": "application/json"},
                                     data=json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "stream": True}).encode())
        result = ""
        with urllib.request.urlopen(req, timeout=20) as response:
            for line in response:
                control.check()
                value = json.loads(line)
                if value.get("error"):
                    raise RuntimeError(str(value["error"]))
                delta = value.get("message", {}).get("content", "")
                result += delta
                control.emit("delta", {"text": delta})
                if value.get("done"):
                    control.emit("usage", {"input_tokens": value.get("prompt_eval_count"), "output_tokens": value.get("eval_count")})
                    return result
        raise RuntimeError("Flux Ollama interrompu avant confirmation finale.")


class NativeLocal(Base):
    kind = 'model'

    def check(self):
        result={'capabilities':['models','stream','cancel'],'native_resume':False}
        if not Path(self.config.get('runtime','')).is_file():
            return {**result,'status':'unconfigured','detail':'Installez le moteur llama.cpp dans les paramètres.'}
        models=self.models()
        if not models:return {**result,'status':'unconfigured','detail':'Moteur installé. Ajoutez un modèle GGUF pour commencer.'}
        manager=getattr(self,'manager',None)
        running=bool(manager and manager.proc and manager.proc.poll() is None and manager.loaded)
        if running:
            name=next((m['name'] for m in models if m['id']==manager.loaded),manager.loaded)
            return {**result,'status':'running','detail':'Modèle chargé : '+name}
        return {**result,'status':'ready','detail':f'{len(models)} modèle(s) disponible(s). Le modèle choisi démarre automatiquement au premier message.'}

    def models(self):
        return [{'id':m['id'],'name':m['name']} for m in self.config.get('models',[]) if Path(m['path']).is_file()]

    def run(self, prompt, root, model, native_id, control):
        if getattr(control,'images',[]):raise ValueError('Le moteur local CyAI ne dispose pas encore du projecteur vision. Choisissez un connecteur compatible images pour analyser ces pièces jointes.')
        manager=self.manager
        if not manager.inference_lock.acquire(blocking=False):raise ValueError('Le moteur local est déjà utilisé par une autre conversation.')
        manager.active_control=control
        finished_watch=threading.Event()
        def watch_cancel():
            while not finished_watch.wait(.1):
                try:control.check()
                except (Cancelled, TimeoutError):
                    # Close the inference process even while HTTP is waiting on prefill.
                    manager.stop()
                    return
        watcher=threading.Thread(target=watch_cancel,daemon=True)
        watcher.start()
        try:
            control.check();manager.start(model,control);control.check()
            if hasattr(control,'plugin_call'):
                from .local_tools import run
                return run(manager.base+'/v1/chat/completions',{'Content-Type':'application/json','Authorization':'Bearer '+manager.key},prompt,control)
            request=urllib.request.Request(manager.base+'/v1/chat/completions',
                headers={'Content-Type':'application/json','Authorization':'Bearer '+manager.key},
                data=json.dumps({'messages':[{'role':'user','content':prompt}],'stream':True,'stream_options':{'include_usage':True}}).encode())
            result='';finished=False
            with urllib.request.urlopen(request,timeout=120) as response:
                for line in response:
                    control.check()
                    if not line.startswith(b'data:'):continue
                    raw=line[5:].strip()
                    if raw==b'[DONE]':
                        if finished:return result
                        break
                    event=json.loads(raw)
                    if event.get('error'):raise RuntimeError(str(event['error']))
                    if event.get('usage'):
                        from .local_tools import normalized_usage
                        control.emit('usage',normalized_usage(event['usage']))
                    for choice in event.get('choices',[]):
                        delta=choice.get('delta',{}).get('content') or ''
                        result+=delta;control.emit('delta',{'text':delta})
                        if choice.get('finish_reason'):
                            if choice['finish_reason']=='length':raise RuntimeError('Limite de sortie atteinte ; réponse partielle dans les événements.')
                            finished=True
            raise RuntimeError('Flux du moteur local interrompu.')
        except Exception:
            control.check()  # A closed HTTP stream after Stop is cancellation, not failure.
            raise
        finally:
            finished_watch.set()
            watcher.join(timeout=6)
            manager.active_control=None
            manager.inference_lock.release()


def registry(config, secrets):
    from .extra_connectors import HeadlessCLI, OpenRouter, CLI_INFO
    classes = {**{key:HeadlessCLI for key in CLI_INFO}, "openrouter":OpenRouter, "codex": Codex, "claude-code": ClaudeCode, "opencode": OpenCode, "anthropic": Anthropic, "ollama": Ollama, 'local':NativeLocal}
    return {id: cls(id, {'enabled':id=='codex',**config.get(id, {})}, secrets) for id, cls in classes.items()}
