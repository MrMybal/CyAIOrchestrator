"""Isolated Python environments for the voice engines that need PyTorch: Pocket TTS and Kyutai STT.

CyAI itself ships no PyTorch. When you ask for one of these engines, it downloads uv (Astral, Apache-2.0, SHA-256
published by GitHub), lets uv fetch a managed Python 3.12, creates one environment per engine in the data folder,
installs the official packages from PyPI, then loads the model once so its weights (Hugging Face) are on disk.
Everything stays under the data folder and the models folder: nothing touches the system Python or its packages.
"""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import threading
import time

from .store import uid

UV_ASSET = 'uv-x86_64-pc-windows-msvc.zip'
ENGINES = {
    # Pocket TTS runs on the processor: its CPU build of PyTorch is enough and leaves the graphics card alone.
    'pocket': {'packages': ['pocket-tts==3.1.0'], 'torch': 'cpu', 'worker': 'pocket.worker',
               'weights': [('kyutai--pocket-tts-without-voice-cloning', 672178676 + 33035296 + 60173)]},
    # Kyutai STT wants the graphics card to follow speech in real time: uv picks the CUDA build matching the driver.
    'kyutai': {'packages': ['moshi==0.2.13'], 'torch': 'auto', 'worker': 'kyutai.worker',
               'weights': [('kyutai--stt-1b-en_fr', 1978423520 + 384644900 + 120378)]},
}


from .voice_expressive import SPECS as EXPRESSIVE_SPECS
ENGINES.update(EXPRESSIVE_SPECS)
from .voice_phonon import SPEC as PHONON_SPEC
ENGINES['phonon'] = PHONON_SPEC

def _hidden():
    return subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0


def folder_size(path):
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


class Environments:
    def __init__(self, voice):
        self.voice = voice

    # Places: all inside CyAI's data folder (programs) or models folder (weights).
    def runtimes(self):
        return self.voice.runtimes_folder()

    def env_dir(self, engine):
        return self.runtimes() / ('voice-' + engine)

    def python(self, engine):
        return self.env_dir(engine) / 'Scripts' / 'python.exe'

    def hf_home(self):
        return self.voice.folder() / 'huggingface'

    def worker(self, engine):
        return Path(__file__).parent / 'voice_workers' / ENGINES[engine]['worker']

    def uv_env(self):
        base = self.runtimes()
        return {'UV_PYTHON_INSTALL_DIR': str(base / 'uv-python'), 'UV_CACHE_DIR': str(base / 'uv-cache'),
                'UV_PYTHON_PREFERENCE': 'only-managed', 'UV_NO_PROGRESS': '1'}

    def worker_env(self):
        env = {'HF_HOME': str(self.hf_home()), 'HF_HUB_DISABLE_TELEMETRY': '1', 'PYTHONIOENCODING': 'utf-8',
               'PYTHONUNBUFFERED': '1', 'PYTHONNOUSERSITE': '1',
               'FERMION_CACHE_DIR': str(self.voice.folder() / 'phonon'), 'FERMION_DEVICE': 'cpu',
               # moshi compiles its model with torch.compile, which needs Triton: not available on Windows.
               'NO_TORCH_COMPILE': '1'}
        secrets = self.voice.service.engine.secrets
        token = secrets.get('huggingface') if hasattr(secrets, 'get') else None
        if token:
            env['HF_TOKEN'] = token  # Only for the voice cloning weights, whose access you accepted on Hugging Face.
        return env

    def record(self, engine):
        record = self.voice.settings()['runtimes'].get(engine) or {}
        if not record and engine in EXPRESSIVE_SPECS:
            manifest=self.env_dir(engine) / 'cyai-install.json'
            try:
                saved=json.loads(manifest.read_text(encoding='utf-8'))
                if saved.get('packages')==ENGINES[engine]['packages'] and Path(saved.get('python','')).resolve()==self.python(engine).resolve(): record=saved
            except (OSError, ValueError, TypeError): pass
        return record

    def installed(self, engine):
        record = self.record(engine)
        return bool(record) and Path(record.get('python', '')).is_file()

    # ----- installation ---------------------------------------------------------------------------------------
    def run(self, args, env, detail, progress, timeout=3600):
        """Runs one installation command, showing its last line in the operation."""
        merged = {**os.environ, **env}
        for name in list(merged):
            if name.startswith('CYAI_') or name.endswith('_API_KEY'):
                merged.pop(name)
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8',
                                errors='replace', env=merged, creationflags=_hidden())
        lines = []
        started = time.monotonic()
        for line in proc.stdout:
            line = line.strip()
            if line:
                lines.append(line)
                progress(0, 0, detail + ' · ' + line[-160:])
            if time.monotonic() - started > timeout:
                proc.kill()
                raise RuntimeError(detail + ' : délai dépassé.')
        if proc.wait():
            raise RuntimeError(detail + ' a échoué : ' + ' | '.join(lines[-6:])[-1500:])
        return lines

    def ensure_uv(self, progress):
        settings = self.voice.settings()
        record = settings['runtimes'].get('uv') or {}
        if Path(record.get('path', '')).is_file():
            return record['path']
        from .connectors import request_json
        from .local_models import download
        from .voice import _extract
        release = request_json('https://api.github.com/repos/astral-sh/uv/releases/latest', headers={'User-Agent': 'CyAI'})
        asset = next((a for a in release['assets'] if a['name'] == UV_ASSET), None)
        if not asset or not asset.get('digest', '').startswith('sha256:'):
            raise ValueError('La publication de uv ne fournit pas d’archive Windows vérifiable.')
        destination = self.runtimes() / ('uv-' + release['tag_name'] + '-' + uid()[:8])
        destination.mkdir(parents=True)
        archive = destination / UV_ASSET
        sha = download(asset['browser_download_url'], archive, lambda r, t: progress(r, t, 'Téléchargement de uv ' + release['tag_name']), asset['digest'])
        _extract(archive, destination)
        archive.unlink()
        executable = next(destination.rglob('uv.exe'), None)
        if not executable:
            raise ValueError('uv.exe absent de l’archive.')
        settings = self.voice.settings()
        settings['runtimes']['uv'] = {'path': str(executable), 'folder': str(destination), 'version': release['tag_name'], 'sha256': sha, 'published_sha': True}
        self.voice.persist(settings)
        return str(executable)

    def install(self, engine, progress):
        spec = ENGINES[engine]
        uv = self.ensure_uv(progress)
        env_dir = self.env_dir(engine).resolve()
        if not env_dir.is_relative_to(self.runtimes().resolve()): raise ValueError('Dossier de moteur hors du dossier des runtimes.')
        manifest=env_dir / 'cyai-install.json'
        if engine in EXPRESSIVE_SPECS and manifest.is_file() and self.python(engine).is_file():
            record=json.loads(manifest.read_text(encoding='utf-8'))
            if record.get('packages')==spec['packages']:
                settings=self.voice.settings(); settings['runtimes'][engine]=record; self.voice.persist(settings)
                progress(1,1,'Installation déjà préparée, activée dans CyAI.')
                return
        if env_dir.exists():
            shutil.rmtree(env_dir)  # A half-installed environment is rebuilt from scratch.
        self.run([uv, 'venv', '--python', '3.12', str(env_dir)], self.uv_env(), 'Python 3.12 isolé', progress)
        args = [uv, 'pip', 'install', '--python', str(self.python(engine)), '--no-cache', '--torch-backend', spec['torch'], *spec['packages']]
        if engine == 'fish':
            from .local_models import download
            from .voice import _extract
            from .voice_expressive import FISH_COMMIT
            archive = env_dir / 'fish-source.zip'
            download('https://github.com/fishaudio/fish-speech/archive/' + FISH_COMMIT + '.zip', archive, lambda r,t: progress(r,t,'Source Fish épinglée'))
            source_root = env_dir / 'source'
            _extract(archive, source_root)
            source = source_root / ('fish-speech-' + FISH_COMMIT)
            args = args[:-len(spec['packages'])] + ['--editable', str(source), *spec['packages'][1:]]
        if spec.get('overrides'):
            overrides = env_dir / 'cyai-overrides.txt'
            overrides.write_text('\n'.join(spec['overrides']), encoding='utf-8')
            args += ['--override', str(overrides)]
        self.run(args, self.uv_env(), 'Paquets ' + ', '.join(spec['packages']) + ' et PyTorch', progress)
        # First load: the weights come from Hugging Face into the models folder, with their size shown as they arrive.
        expected = sum(size for _, size in spec['weights'])
        hub = self.hf_home() / 'hub'
        weight_folders = [(self.hf_home() / 'models' / name) if engine in EXPRESSIVE_SPECS else (hub / ('models--'+name)) for name, _ in spec['weights']]
        downloaded_size = lambda: sum(folder_size(path) for path in weight_folders)
        if spec.get('cache_folder'):
            weight_folders = [self.voice.folder() / spec['cache_folder']]
        before = downloaded_size()
        done = threading.Event()

        def watch():
            while not done.wait(1):
                progress(max(0, downloaded_size() - before), expected, 'Poids du modèle (Hugging Face)')
        threading.Thread(target=watch, daemon=True).start()
        try:
            self.run([str(self.python(engine)), str(self.worker(engine)), 'prepare'] + ([engine] if engine in EXPRESSIVE_SPECS else []), self.worker_env(), 'Premier chargement du modèle', progress, 7200)
        finally:
            done.set()
        version = self.run([str(self.python(engine)), '-c', 'import importlib.metadata as m, torch;'
                            f'print(m.version("{spec.get("distribution", spec["packages"][0].split("==")[0])}"), torch.__version__, torch.cuda.is_available())'],
                           self.worker_env(), 'Vérification', progress)[-1]
        settings = self.voice.settings()
        settings['runtimes'][engine] = {'python': str(self.python(engine)), 'folder': str(env_dir), 'version': version,
                                        'packages': spec['packages'], 'torch': spec['torch']}
        if engine in EXPRESSIVE_SPECS:
            manifest.write_text(json.dumps(settings['runtimes'][engine]),encoding='utf-8')
        self.voice.persist(settings)

    def remove(self, engine):
        settings = self.voice.settings()
        record = settings['runtimes'].pop(engine, None)
        folder = self.env_dir(engine).resolve()
        if folder.is_relative_to(self.runtimes().resolve()) and folder.exists():
            shutil.rmtree(folder)
        for name, _ in ENGINES[engine]['weights']:
            cache = (self.hf_home() / 'hub' / ('models--' + name)).resolve()
            if cache.is_relative_to(self.voice.folder().resolve()) and cache.exists():
                shutil.rmtree(cache, ignore_errors=True)
        if engine in EXPRESSIVE_SPECS:
            for name, _ in ENGINES[engine]['weights']:
                model_dir=(self.hf_home() / 'models' / name).resolve()
                if model_dir.is_relative_to(self.voice.folder().resolve()) and model_dir.exists(): shutil.rmtree(model_dir)
        if ENGINES[engine].get('cache_folder'):
            cache = (self.voice.folder() / ENGINES[engine]['cache_folder']).resolve()
            if cache.is_relative_to(self.voice.folder().resolve()) and cache.exists(): shutil.rmtree(cache)
        self.voice.persist(settings)
        return record

    def verify(self, engine):
        if not self.installed(engine):
            return {'ok': False, 'detail': 'Environnement absent : installez-le.'}
        result = subprocess.run([str(self.python(engine)), '-c', 'import torch;import ' + ENGINES[engine].get('module', 'pocket_tts' if engine == 'pocket' else 'moshi')],
                                capture_output=True, text=True, timeout=300, env={**os.environ, **self.worker_env()}, creationflags=_hidden())
        ok = result.returncode == 0
        return {'ok': ok, 'detail': 'Environnement complet.' if ok else 'Environnement incomplet : ' + (result.stderr or '')[-400:]}


# ----- engines running in those environments ------------------------------------------------------------------
class _Worker:
    """A worker process speaking JSON lines; the first line it writes says the model is loaded."""

    def __init__(self, args, env, cwd, ready_timeout=900):
        from .connectors import spawn
        self.proc = spawn(args, cwd, env)
        self.logs, self.used = [], time.monotonic()
        self.listeners = []
        self.answers = __import__('queue').Queue()
        threading.Thread(target=self._stderr, daemon=True).start()
        threading.Thread(target=self._stdout, daemon=True).start()
        try:
            first = self.next(ready_timeout)
        except Exception:
            self.close()
            raise
        if not first.get('ok'):
            self.close()
            raise RuntimeError(first.get('error') or 'Le moteur n’a pas démarré.')
        self.info = first

    def _stderr(self):
        for line in self.proc.stderr:
            self.logs = (self.logs + [line.strip()])[-40:]

    def _stdout(self):
        for line in self.proc.stdout:
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if 'piece' in message:
                for listener in self.listeners:
                    listener(message['piece'])
                continue
            self.answers.put(message)
        self.answers.put({'ok': False, 'error': 'Le moteur s’est arrêté : ' + ' | '.join(self.logs[-4:])[-600:]})

    def next(self, timeout):
        import queue
        try:
            return self.answers.get(timeout=timeout)
        except queue.Empty:
            raise RuntimeError('Le moteur ne répond pas : ' + ' | '.join(self.logs[-4:])[-600:])

    def send(self, message):
        self.used = time.monotonic()
        self.proc.stdin.write(json.dumps(message, ensure_ascii=True) + '\n')
        self.proc.stdin.flush()

    def alive(self):
        return self.proc.poll() is None

    def idle_for(self):
        return time.monotonic() - self.used

    def close(self):
        if self.alive():
            from .connectors import stop_process
            stop_process(self.proc)
        for pipe in (self.proc.stdin, self.proc.stdout, self.proc.stderr):
            if pipe:
                try: pipe.close()
                except OSError: pass


class PocketTTS:
    """Natural voices of Kyutai's Pocket TTS, on the processor; a WAV sample gives a copied voice."""

    def __init__(self, environments, language):
        self.environments, self.language = environments, language
        self.folder = Path(__import__('tempfile').mkdtemp(prefix='cyai-pocket-'))
        self.worker = None
        self.lock = threading.Lock()
        self.clone_attempted = False

    def _ensure_worker(self, voice):
        cloning = str(voice).lower().endswith('.wav')
        if self.worker and self.worker.alive() and cloning and not self.worker.info.get('cloning') and not self.clone_attempted:
            self.worker.close()
            self.worker = None
        if not self.worker or not self.worker.alive():
            env = self.environments
            # Only an explicit copied-voice request may fetch its authorised weights.
            # The WAV stays local; Hugging Face receives only model download requests.
            worker_env = {**env.worker_env(), 'HF_HUB_OFFLINE': '0' if cloning else '1'}
            self.worker = _Worker([str(env.python('pocket')), str(env.worker('pocket')), 'serve', self.language],
                                  worker_env, str(self.folder))
            self.clone_attempted = cloning

    def synthesize(self, text, voice, temperature=None):
        with self.lock:
            self._ensure_worker(voice)
            target = self.folder / ('%d.wav' % time.monotonic_ns())
            self.worker.send({'text': ' '.join(text.split()), 'voice': voice, 'file': str(target), 'temperature': temperature})
            answer = self.worker.next(300)
        if not answer.get('ok'):
            raise RuntimeError(answer.get('error') or 'Pocket TTS n’a pas produit de son.')
        data = target.read_bytes()
        target.unlink(missing_ok=True)
        return data

    def synthesize_stream(self, text, voice, on_audio, stop, temperature=None):
        """Deliver PCM chunks immediately; drain the worker even after interruption to keep its protocol aligned."""
        import base64
        with self.lock:
            self._ensure_worker(voice)
            self.worker.send({'text': ' '.join(text.split()), 'voice': voice, 'stream': True, 'temperature': temperature})
            while True:
                answer = self.worker.next(300)
                if 'audio' in answer:
                    if not stop():
                        from .voice_audio import wav_bytes
                        on_audio(wav_bytes(base64.b64decode(answer['audio']), answer['rate']))
                elif not answer.get('ok'):
                    raise RuntimeError(answer.get('error') or 'Synthèse interrompue.')
                else:
                    break

    def idle_for(self):
        return self.worker.idle_for() if self.worker else None

    def close(self):
        if self.worker:
            self.worker.close()
            self.worker = None


class KyutaiSTT:
    """Kyutai's streaming recogniser: words arrive while you speak; the final text comes at the end."""
    RATE = 24000

    def __init__(self, environments, device):
        env = environments
        # All its weights came with the installation: no need to ask Hugging Face again at each start.
        self.worker = _Worker([str(env.python('kyutai')), str(env.worker('kyutai')), 'serve', device],
                              {**env.worker_env(), 'HF_HUB_OFFLINE': '1'}, str(env.runtimes()))
        self.partial = ''
        self.worker.listeners.append(self._piece)

    def _piece(self, piece):
        self.partial += piece

    def begin(self):
        self.partial = ''
        self.worker.send({'op': 'start'})

    def feed(self, pcm):
        import base64
        self.worker.send({'op': 'audio', 'pcm': base64.b64encode(pcm).decode()})

    def finish(self):
        self.worker.send({'op': 'end'})
        answer = self.worker.next(120)
        if not answer.get('ok'):
            raise RuntimeError(answer.get('error') or 'La dictée Kyutai a échoué.')
        return answer.get('final', self.partial)

    def alive(self):
        return self.worker.alive()

    def idle_for(self):
        return self.worker.idle_for()

    def close(self):
        self.worker.close()


POCKET_LANGUAGES = {'french_24l': 'Français', 'english': 'Anglais'}
# Voices published with Pocket TTS. The French model has an embedding for each of them: they all speak French,
# « estelle » being the French speaker.
POCKET_VOICES = ['estelle', 'alba', 'anna', 'azelma', 'bill_boerst', 'caro_davy', 'charles', 'cosette', 'eponine', 'eve',
                 'fantine', 'george', 'jane', 'javert', 'jean', 'marius', 'mary', 'michael', 'paul', 'peter_yearsley',
                 'stuart_bell', 'vera']


def safe_name(value):
    return re.sub(r'[^\w .’\'-]', '', str(value or '')).strip()[:60]
