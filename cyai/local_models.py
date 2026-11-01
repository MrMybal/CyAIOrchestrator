"""Managed llama.cpp runtime and GGUF downloads, independent of Ollama."""
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import socket
import threading
import time
import urllib.request
import urllib.parse
import zipfile

from .connectors import request_json, spawn, stop_process
from .store import uid


def download(url, target, progress, expected_sha=''):
    part = target.with_suffix(target.suffix + '.part')
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError('Ce fichier existe déjà.')
    digest = hashlib.sha256()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':'CyAI-Orchestrator'}), timeout=30) as response, part.open('wb') as output:
            total = int(response.headers.get('Content-Length', 0))
            received = 0
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk: break
                output.write(chunk); digest.update(chunk); received += len(chunk)
                progress(received, total)
        if expected_sha and digest.hexdigest() != expected_sha.removeprefix('sha256:'):
            raise ValueError('Somme SHA-256 différente de celle publiée ; téléchargement rejeté.')
        part.replace(target)
        return digest.hexdigest()
    finally:
        part.unlink(missing_ok=True)


def runtime_args(executable, model, config, port, key):
    device = config.get('device', 'cpu')
    if device not in {'cpu','gpu','hybrid'}: raise ValueError('Mode de calcul invalide.')
    layers = 0 if device == 'cpu' else 999 if device == 'gpu' else int(config.get('gpu_layers', 16))
    threads, context = int(config.get('threads', 4)), int(config.get('context', 4096))
    if not 0 <= layers <= 999 or not 1 <= threads <= 256 or not 512 <= context <= 131072:
        raise ValueError('Réglages de calcul hors limites.')
    return [str(executable), '-m', str(model), '--host', '127.0.0.1', '--port', str(port),
            '--api-key', key, '--n-gpu-layers', str(layers), '--threads', str(threads), '--ctx-size', str(context), '--parallel', '1']


class LocalModels:
    def __init__(self, service):
        self.service = service
        self.config = service.engine.connectors['local'].config
        self.pending = deque(); self.worker_active = False
        self.jobs = {}; self.lock = threading.RLock(); self.proc = None
        self.logs = deque(maxlen=100); self.loaded = None; self.base = ''; self.key = ''
        self.inference_lock = threading.Lock()
        self.active_control = None
        # Adopt a completed standalone installation without touching the live app config.
        try:
            record=json.loads((service.store.path.parent/'runtimes'/'prism-runtime.json').read_text(encoding='utf-8'))
            if not self.config.get('prism_runtime') and Path(record['runtime']).is_file():
                self.config.update(prism_runtime=record['runtime'],prism_backend=record['backend'])
        except (OSError,ValueError,KeyError,AttributeError):pass

    def folder(self):
        return Path(self.config.get('models_dir') or self.service.store.path.parent / 'models').resolve()

    def persist(self):
        self.service.config.setdefault('connectors', {})['local'] = self.config
        self.service.plugins.persist()

    def state(self):
        from .model_memory import hardware, gguf_estimate
        hw = hardware()
        models = [{**m,'effective_settings':{k:{**self.config,**m.get('settings',{})}.get(k,d) for k,d in [('device','cpu'),('gpu_layers',16),('threads',4),('context',4096)]},'exists':Path(m['path']).is_file()} for m in self.config.get('models', [])]
        models = [{**m, 'memory':gguf_estimate(m,hw), 'runtime_family':self.runtime_family(m)} for m in models]
        return {'hardware':hw,'prism_runtime':self.config.get('prism_runtime',''),'models':models,'models_dir':str(self.folder()),'settings':{k:self.config.get(k,d) for k,d in [('device','cpu'),('gpu_layers',16),('threads',4),('context',4096),('backend','cpu')]},
                'runtime':self.config.get('runtime',''),'running':bool(self.proc and self.proc.poll() is None),'loaded':self.loaded,
                'jobs':list(self.jobs.values()),'logs':list(self.logs),'components':self.service.components.state()}

    def job(self, name, function):
        with self.lock:
            existing=next((j for j in self.jobs.values() if j['name']==name and j['status'] in {'queued','running'}),None)
            if existing:return {'job_id':existing['id'],'status':existing['status']}
            identifier=uid();item={'id':identifier,'name':name,'status':'queued','received':0,'total':0}
            self.jobs[identifier]=item;self.pending.append((item,function))
            if not self.worker_active:
                self.worker_active=True
                threading.Thread(target=self._run_jobs,daemon=True).start()
            return {'job_id':identifier,'status':item['status']}

    def _run_jobs(self):
        while True:
            with self.lock:
                if not self.pending:
                    self.worker_active=False
                    return
                item,function=self.pending.popleft();item['status']='running'
            try:
                # A step may also describe itself (installing a Python environment has no byte count).
                function(lambda received,total,detail=None:item.update(received=received,total=total,**({'detail':detail} if detail else {})))
                item['status']='succeeded'
            except Exception as exc:
                item.update(status='failed',error=self.service.engine.secrets.redact(str(exc)))
                try:self.service.store.log('error','local_models.'+item['name'],item['error'])
                except Exception:pass  # A logging failure must not strand subsequent jobs.

    @staticmethod
    def runtime_family(model):
        chosen=model.get('settings',{}).get('runtime_family')
        if chosen in {'standard','prism'}:return chosen
        text = (model.get('name','')+' '+model.get('path','')).lower()
        return 'prism' if 'bonsai-2' in text or 'bonsai 2' in text or 'ptq1_0' in text else 'standard'

    def install_runtime(self, backend):
        prism = backend.startswith('prism-')
        if prism: backend = backend[6:]
        if backend not in {'cpu','vulkan','cuda'}: raise ValueError('Backend invalide.')
        def install(progress):
            releases=request_json('https://api.github.com/repos/'+('PrismML-Eng' if prism else 'ggml-org')+'/llama.cpp/releases?per_page=10',headers={'User-Agent':'CyAI'})
            suffix={'cpu':'bin-win-cpu-x64.zip','vulkan':'bin-win-vulkan-x64.zip','cuda':'bin-win-cuda-12.4-x64.zip'}[backend]
            release=next((r for r in releases if any(a['name'].startswith('llama-') and a['name'].endswith(suffix) for a in r['assets'])),None)
            if not release: raise ValueError('Aucune distribution Windows x64 compatible publiée.')
            assets=[next(a for a in release['assets'] if a['name'].startswith('llama-') and a['name'].endswith(suffix))]
            if backend=='cuda':assets.append(next(a for a in release['assets'] if a['name']=='cudart-llama-bin-win-cuda-12.4-x64.zip'))
            destination=self.service.store.path.parent/'runtimes'/('llama-'+release['tag_name']+'-'+backend+'-'+uid()[:8])
            destination.mkdir(parents=True)
            for asset in assets:
                if not asset.get('digest','').startswith('sha256:'): raise ValueError('La publication ne fournit pas de SHA-256 vérifiable.')
                archive=destination/asset['name']
                download(asset['browser_download_url'],archive,progress,asset['digest'])
                with zipfile.ZipFile(archive) as z:
                    for member in z.infolist():
                        path=(destination/member.filename).resolve()
                        if not path.is_relative_to(destination.resolve()) or (member.external_attr >> 16) & 0o170000 == 0o120000:
                            raise ValueError('Archive du moteur invalide.')
                    z.extractall(destination)
                archive.unlink()
            executable=next(destination.rglob('llama-server.exe'))
            if backend=='cuda':
                for dll in destination.rglob('*.dll'):
                    if dll.parent!=executable.parent and not (executable.parent/dll.name).exists():shutil.copy2(dll,executable.parent/dll.name)
            if prism:
                self.config.update(prism_runtime=str(executable),prism_backend=backend)
                record=destination.parent/'prism-runtime.json'
                pending=record.with_suffix('.tmp')
                pending.write_text(json.dumps({'runtime':str(executable),'backend':backend,'release':release['tag_name']}),encoding='utf-8')
                pending.replace(record)
            else:self.config.update(runtime=str(executable),backend=backend)
            self.persist()
        return self.job('Installation '+('PrismML ' if prism else 'llama.cpp ')+backend, install)

    def remote_files(self, repo):
        if not re.fullmatch(r'[\w.-]+/[\w.-]+',repo): raise ValueError('Indiquez un dépôt Hugging Face sous la forme auteur/modèle.')
        info=request_json('https://huggingface.co/api/models/'+repo+'?blobs=true')
        return {'repo':repo,'revision':info['sha'],'files':[{'name':f['rfilename'],'bytes':f.get('size',f.get('lfs',{}).get('size',0)),'sha256':f.get('lfs',{}).get('sha256','')} for f in info.get('siblings',[]) if f['rfilename'].lower().endswith('.gguf') and not f['rfilename'].lower().startswith('mmproj')]}

    def add(self, path, name, sha=''):
        with path.open('rb') as f:
            if f.read(4)!=b'GGUF': raise ValueError('Le fichier ne contient pas un modèle GGUF.')
        model={'id':uid(),'name':name,'path':str(path),'bytes':path.stat().st_size,'sha256':sha,'settings':{}}
        self.config.setdefault('models',[]).append(model);self.persist();return model

    def install_model(self, repo, filename):
        info=self.remote_files(repo)
        model=next((f for f in info['files'] if f['name']==filename),None)
        if not model: raise ValueError('Fichier GGUF absent du dépôt.')
        if re.search(r'-\d{5}-of-\d{5}\.gguf$',filename):raise ValueError('Choisissez un GGUF monofichier ; les modèles fractionnés ne sont pas encore pris en charge.')
        target=self.folder()/(repo.replace('/','--')+'--'+Path(filename).name)
        def install(progress):
            sha=download('https://huggingface.co/'+repo+'/resolve/'+info['revision']+'/'+urllib.parse.quote(filename,safe='/'),target,progress,model['sha256'])
            self.add(target,repo+' / '+filename,sha)
        return self.job('Téléchargement '+repo+' / '+filename,install)

    def start(self, identifier, control=None):
        with self.lock:
            if self.proc and self.proc.poll() is None and self.loaded==identifier:return
            self.stop()
            model=next((m for m in self.config.get('models',[]) if m['id']==identifier),None)
            if not model:raise ValueError('Choisissez un modèle GGUF installé.')
            settings={**self.config,**model.get('settings',{})}
            prism = self.runtime_family(model)=='prism'
            executable=Path(self.config.get('prism_runtime' if prism else 'runtime',''))
            if prism and not executable.is_file():raise ValueError('Bonsai 2 nécessite PrismML. Paramètres → Modèles locaux → Installer PrismML CUDA (ou CPU/Vulkan). Le moteur standard reste conservé.')
            if not executable.is_file():raise ValueError('Installez le moteur llama.cpp dans les paramètres.')
            if settings.get('device','cpu')!='cpu' and self.config.get('prism_backend' if prism else 'backend','cpu')=='cpu':raise ValueError('Installez la version Vulkan ou CUDA pour utiliser le GPU.')
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            self.key=secrets.token_urlsafe(32);self.base='http://127.0.0.1:'+str(port);self.logs.clear()
            if control:control.check()
            self.proc=spawn(runtime_args(executable,model['path'],settings,port,self.key),str(executable.parent))
            if control and control.cancelled.is_set():
                self.stop();control.check()
            def drain(stream):
                for line in stream:self.logs.append(line.strip())
            for stream in (self.proc.stdout,self.proc.stderr):threading.Thread(target=drain,args=(stream,),daemon=True).start()
            self.loaded=identifier
            while True:
                if control:control.check()
                if self.proc is None:raise RuntimeError("Chargement arrêté par l’utilisateur.")
                if self.proc.poll() is not None:raise RuntimeError('llama.cpp n’a pas démarré : '+'\n'.join(self.logs)[-5000:])
                try:
                    request_json(self.base+'/health',headers={'Authorization':'Bearer '+self.key},timeout=1)
                    return
                except (OSError,ValueError):time.sleep(.5)

    def stop(self):
        proc=self.proc
        if proc:
            stop_process(proc)
            proc.wait(timeout=5)
            if proc.poll() is None:raise RuntimeError('Le moteur local ne s’est pas arrêté ; la mémoire peut encore être occupée.')
        self.proc=None;self.loaded=None
        self.base='';self.key=''

    def action(self, action, d):
        if action=='local_state':return self.state()
        if action=='local_catalog':
            return json.loads((Path(__file__).parent/'web'/'local-catalog.json').read_text(encoding='utf-8'))
        if action=='local_model_settings':
            if self.inference_lock.locked() or self.proc and self.proc.poll() is None:
                raise ValueError('Arrêtez le moteur avant de modifier les réglages d’un modèle.')
            model=next((m for m in self.config.get('models',[]) if m['id']==d['id']),None)
            if not model:raise ValueError('Modèle absent.')
            values=d.get('settings',{})
            clean={k:values[k] for k in ('device','gpu_layers','threads','context','runtime_family') if values.get(k) not in (None,'')}
            if clean.get('runtime_family') not in (None,'standard','prism'):raise ValueError('Moteur : automatique, standard ou prism.')
            runtime_args('server','model',{**self.config,**clean},1,'key')
            model['settings']=clean;self.persist();return {'ok':True}
        if action=='local_runtime_install':return self.install_runtime(d.get('backend','cpu'))
        if action=='local_model_files':return self.remote_files(d['repo'])
        if action=='local_model_install':return self.install_model(d['repo'],d['filename'])
        if action=='local_model_import':
            from .windows_ui import choose_file
            path=choose_file()
            if not path:return {'cancelled':True}
            source=Path(path)
            if source.suffix.lower()!='.gguf':raise ValueError('Sélectionnez un fichier GGUF.')
            def copy(progress):
                target=self.folder()/source.name;target.parent.mkdir(parents=True,exist_ok=True)
                if target.exists() and target!=source:raise ValueError('Un modèle de ce nom existe déjà.')
                if target!=source:shutil.copy2(source,target)
                self.add(target,source.stem)
            return self.job('Import GGUF',copy)
        if action=='local_settings':
            if self.proc and self.proc.poll() is None:raise ValueError('Arrêtez le modèle avant de modifier ses réglages.')
            candidate={**self.config,**{k:d[k] for k in ('device','gpu_layers','threads','context') if k in d}}
            runtime_args('server','model',candidate,1,'key')
            if d.get('models_dir'):
                folder=Path(d['models_dir']).expanduser()
                if not folder.is_absolute():raise ValueError('Le dossier doit être absolu.')
                candidate['models_dir']=str(folder.resolve())
            self.config.update(candidate);self.persist();return {'ok':True}
        if action=='local_start':return self.job('Chargement du modèle',lambda _:self.start(d['id']))
        if action=='local_stop':
            if self.active_control:self.active_control.cancelled.set()
            elif self.inference_lock.locked():raise ValueError('Démarrage de la conversation en cours ; réessayez Arrêter dans un instant.')
            self.stop();return {'ok':True}
        return None
