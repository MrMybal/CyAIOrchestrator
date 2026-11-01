"""Public headless CLI adapters and OpenRouter; no GUI automation or credential scraping."""
import json
import hashlib
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
from collections import deque

from .connectors import Base, executable, spawn, stop_process, request_json

CLI_INFO = {
 'command-code': ('Command Code', 'command-code', 'https://commandcode.ai/docs/headless'),
 'codebuddy': ('CodeBuddy · Tencent', 'codebuddy', 'https://www.codebuddy.ai/docs/cli/headless'),
 'antigravity': ('Antigravity · Google', 'agy', 'https://antigravity.google/docs/cli/headless/'),
 'devin': ('Devin CLI · Cognition', 'devin', 'https://docs.devin.ai/cli/reference/commands'),
}


def cli_events(args, root, control, input_text):
    """Drain both pipes while remaining cancellable, even when the agent is silent."""
    control.check()
    proc=spawn(args,root);inbox=queue.Queue();errors=deque(maxlen=30);write_errors=[];write_done=threading.Event()
    def stdout():
        try:
            for line in proc.stdout:inbox.put(line)
        finally:inbox.put(None)
    def stderr():
        for line in proc.stderr:errors.append(line.rstrip())
    def write():
        try:proc.stdin.write(input_text);proc.stdin.close()
        except (OSError,ValueError) as error:write_errors.append(str(error))
        finally:write_done.set()
    readers=[threading.Thread(target=fn,daemon=True) for fn in (stdout,stderr,write)]
    for thread in readers:thread.start()
    try:
        while True:
            control.check()
            try:line=inbox.get(timeout=.1)
            except queue.Empty:continue
            if line is None:break
            yield line
        while proc.poll() is None:
            control.check()
            try:proc.wait(timeout=.1)
            except subprocess.TimeoutExpired:pass
        readers[1].join(timeout=1)
        if write_errors:raise RuntimeError('Transmission du prompt au CLI interrompue : '+'; '.join(write_errors))
        if not write_done.is_set():raise RuntimeError('Le CLI a terminé avant confirmation de l’envoi du prompt.')
        if proc.returncode:
            raise RuntimeError('CLI terminé avec le code '+str(proc.returncode)+' : '+'\n'.join(errors))
    finally:
        stop_process(proc)
        proc.wait(timeout=5)
        for stream in (proc.stdin,proc.stdout,proc.stderr):
            try:stream.close()
            except (OSError,ValueError):pass


class HeadlessCLI(Base):
    native_cli=True
    def command(self):return executable(self.config.get('executable') or CLI_INFO[self.id][1])
    def check(self):
        try:self.command()
        except ValueError as exc:return {'status':'unconfigured','detail':str(exc),'documentation':CLI_INFO[self.id][2]}
        detail='CLI détecté. Connexion à effectuer dans son terminal ; authentification non vérifiée ici.'
        if self.id=='antigravity':
            try:
                m=self.models()
                if m:detail=f'CLI détecté et authentifié ({len(m)} modèle(s) disponibles).'
            except Exception:pass
        return {'status':'installed','detail':detail,
                'capabilities':['stream','cancel','resume','tools'],'documentation':CLI_INFO[self.id][2],
                'native_resume':True,'approval_scope':'native_run'}
    def models(self):
        command={'command-code':['--list-models'],'antigravity':['models'],'devin':['models','list','--format','json']}.get(self.id)
        if not command:
            return [{'id':self.config['model'],'name':self.config['model']}] if self.config.get('model') else []
        result=subprocess.run(self.command()+command,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=30,
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        if result.returncode:raise ValueError('Catalogue indisponible : connectez le CLI dans son terminal. '+result.stderr[-1000:])
        try:
            payload=json.loads(result.stdout)
            rows=payload if isinstance(payload,list) else payload.get('models',payload.get('data',[]))
            return [{'id':r if isinstance(r,str) else r.get('id',r.get('slug',r.get('name'))),'name':r if isinstance(r,str) else r.get('name',r.get('id',r.get('slug')))} for r in rows if isinstance(r,str) or isinstance(r,dict) and (r.get('id') or r.get('slug') or r.get('name'))]
        except (ValueError,AttributeError,TypeError):
            if self.id=='antigravity':
                rows=[]
                for line in result.stdout.splitlines():
                    if '\t' in line:
                        mid,mname=line.strip().split('\t',1)
                        rows.append({'id':mid.strip(),'name':mname.strip()})
                if rows:return rows
            return [{'id':self.config['model'],'name':self.config['model']}] if self.config.get('model') else []

    def arguments(self,root,model,native_id,control,folder):
        args=self.command();planning=getattr(control,'planning',False)
        if planning and self.id in {'devin','antigravity'}:
            raise ValueError('Utilisez Codex, Claude Code, Command Code ou CodeBuddy pour préparer le plan. Ce connecteur est disponible pour son exécution et le tchat.')
        full=bool(self.config.get('native_auto_approve')) and not planning and not getattr(control,'benchmark',False)
        if not planning and not control.approve({'provider':self.id,'kind':'native_run','root':root,'automatic_native_tools':full,
                'notice':'Lancer cet agent local dans le projet. Les outils sont contrôlés par sa politique native ; CyAI ne relaie pas chaque autorisation. Le mode outils automatiques, si activé, autorise les écritures et commandes de cet agent.'}):
            raise ValueError('Exécution du CLI refusée.')
        if self.id=='command-code':
            args+=['-p','--output-format','json','--skip-onboarding']
            if planning:args+=['--plan']
            if full:args+=['--yolo']
        elif self.id=='codebuddy':
            args+=['-p','--output-format','stream-json','--input-format','stream-json','--verbose']
            if planning:args+=['--permission-mode','plan','--tools','Read,Glob,Grep']
            if full:args+=['--permission-mode','bypassPermissions']
            mcp=Path(folder)/'mcp.json';mcp.write_text(json.dumps({'mcpServers':getattr(control,'mcp_servers',{})}),encoding='utf-8')
            args+=['--mcp-config',str(mcp),'--strict-mcp-config']
        elif self.id=='antigravity':
            args+=['--input-format','stream-json','--output-format','stream-json']
            if full:args+=['--dangerously-skip-permissions']
        else:
            args+=['-p','--prompt-file',str(Path(folder)/'prompt.txt'),'--export',str(Path(folder)/'session.json')]
            if full:args+=['--permission-mode','dangerous','--respect-workspace-trust','false']
        if model:args+=['--model',model]
        if native_id:args+=['--conversation' if self.id=='antigravity' else '--resume',native_id]
        return args

    def run(self,prompt,root,model,native_id,control):
        if getattr(control,'images',[]) and self.id!='codebuddy':
            raise ValueError('Images non prises en charge par ce connecteur CyAI. Choisissez un connecteur visuel pour ces pièces jointes.')
        while True:
            control.check()
            with tempfile.TemporaryDirectory(prefix='cyai-cli-') as folder:
                Path(folder,'prompt.txt').write_text(prompt,encoding='utf-8')
                args=self.arguments(root,model,native_id,control,folder)
                if self.id=='codebuddy':
                    blocks=[{'type':'text','text':prompt}]+[{'type':'image','source':{'type':'base64','media_type':im['mime'],'data':im['data']}} for im in getattr(control,'images',[])]
                    input_text=json.dumps({'type':'user','message':{'role':'user','content':blocks}})+'\n'
                elif self.id=='antigravity':input_text=json.dumps({'event':'user','message':{'content':prompt}})+'\n'
                else:input_text=prompt if self.id=='command-code' else ''
                if self.id not in {'codebuddy'} and getattr(control,'mcp_servers',{}):
                    control.emit('warning',{'message':'Ce CLI utilise sa configuration MCP native. Le MCP CyAI temporaire n’est pas injecté automatiquement.'})
                control.emit('transport',{'stage':'prepared','prompt_chars':len(prompt),'prompt_utf8_bytes':len(prompt.encode('utf-8')),'prompt_sha256':hashlib.sha256(prompt.encode('utf-8')).hexdigest(),'stdin_utf8_bytes':len(input_text.encode('utf-8')),'provider':self.id})
                result=None;partial=[];resume_at_limit=False
                try:
                    for line in cli_events(args,root,control,input_text):
                        if self.id=='devin':partial.append(line);control.emit('delta',{'text':line});continue
                        try:event=json.loads(line)
                        except ValueError:control.emit('warning',{'message':line.strip()});continue
                        kind=event.get('type',event.get('event'))
                        payload=event.get('result') if self.id=='antigravity' and kind=='result' else event
                        if not isinstance(payload,dict):payload=event
                        sid=payload.get('sessionId') or payload.get('session_id') or payload.get('conversation_id')
                        if sid:native_id=sid;control.emit('session',{'native_id':sid})
                        if kind=='result':
                            result=payload.get('finalText',payload.get('response',payload.get('result','')))
                            if payload.get('usage'):control.emit('usage',payload['usage'])
                            subtype=payload.get('subtype',payload.get('status','success'))
                            if subtype=='max_turns' and self.id=='command-code' and native_id:
                                resume_at_limit=True
                                control.emit('activity',{'detail':'Limite native de tours : poursuite dans la même session.'})
                            elif payload.get('is_error') or subtype not in {'success','SUCCESS'} or payload.get('denied_actions'):
                                reason=payload.get('error')
                                if payload.get('denied_actions'):
                                    reason='Actions refusées par le CLI : '+json.dumps(payload['denied_actions'],ensure_ascii=False)
                                raise RuntimeError(str(reason or (result if payload.get('is_error') else None) or ('Échec du CLI : '+str(subtype))))
                        elif kind=='step_update':
                            step=event.get('step_update',{})
                            if step.get('text_delta'):control.emit('delta',{'text':step['text_delta']})
                            if step.get('tool_info'):control.emit('tool',step['tool_info'])
                            if step.get('usage'):control.emit('usage',step['usage'])
                        elif kind=='assistant':
                            for block in event.get('message',{}).get('content',[]):
                                if block.get('type')=='text':control.emit('delta',{'text':block.get('text','')})
                                if block.get('type')=='tool_use':control.emit('tool',block)
                        else:control.emit('activity',{'name':str(kind),'event':event})
                except RuntimeError:
                    if not resume_at_limit:raise
                if self.id=='devin':
                    exported=Path(folder,'session.json')
                    if exported.is_file():
                        data=json.loads(exported.read_text(encoding='utf-8'));sid=data.get('session_id')
                        if sid:control.emit('session',{'native_id':sid})
                    return ''.join(partial)
                if resume_at_limit:
                    prompt='Continue la tâche en cours depuis la session conservée, sans répéter les actions déjà terminées.'
                    continue
                if result is None:raise RuntimeError('Flux du CLI fermé sans résultat final. Consultez son authentification et ses permissions.')
                return str(result)


class OpenRouter(Base):
    kind='model'
    def headers(self):
        key=self.secrets.get('openrouter')
        if not key:raise ValueError('Ajoutez votre clé OpenRouter dans les paramètres du connecteur.')
        return {'Authorization':'Bearer '+key,'Content-Type':'application/json','X-Title':'CyAI Orchestrator'}
    def check(self):
        self.headers()
        return {'status':'configured','detail':'API OpenRouter configurée ; clé à vérifier.','capabilities':['models','stream','tools','cancel'],'native_resume':False}
    def models(self):
        payload=request_json('https://openrouter.ai/api/v1/models',headers=self.headers())
        return [{'id':m['id'],'name':m.get('name',m['id']),'context_length':m.get('context_length'),'pricing':m.get('pricing',{}),'input_modalities':m.get('architecture',{}).get('input_modalities',[])} for m in payload['data']]
    def run(self,prompt,root,model,native_id,control):
        if not model:raise ValueError('Choisissez un modèle dans le catalogue OpenRouter.')
        from .local_tools import run
        return run('https://openrouter.ai/api/v1/chat/completions',self.headers(),prompt,control,model=model)
