"""Voice in CyAI conversations: dictation (speech to text) and spoken answers (text to speech), all local.

- The voice is only ever switched on by the user: a click on the microphone 🎙, on the direct discussion 🗣 or on
  « Lire les réponses ». Nothing of it is restored at start-up, and no agent can switch it on (no MCP tool).
- The voice never chooses an AI. A transcript goes back to the page, which sends it exactly like a typed message,
  with the connector, model and context of the composer.
- Only the text of an answer is read: never its thinking, tools, events, code or the continuity block. Answers of
  several steps are read one after the other, each with the voice of its agent.
- Recordings live in memory until they are transcribed, then are dropped.
"""
from collections import OrderedDict, deque
import hashlib
import json
import queue
from pathlib import Path
import re
import shutil
import threading
import time
import urllib.parse
import zipfile

from .store import now, uid
from .voice_python import POCKET_LANGUAGES, POCKET_VOICES, Environments, KyutaiSTT, PocketTTS, safe_name
from .voice_text import Segmenter, planning_reply, speakable, usable_transcript

UNHANDLED = object()
BUSY = ('pending', 'queued', 'running', 'awaiting_approval', 'pausing', 'paused')
# Connectors whose streamed text is the answer itself (their thinking and tools arrive as other events).
# The others are read when their answer is complete, from the message CyAI keeps.
STREAMED = {'codex', 'claude-code', 'anthropic', 'ollama', 'local', 'openrouter'}
AGENTS = {'codex': 'Codex', 'claude-code': 'Claude Code', 'anthropic': 'Claude', 'ollama': 'Ollama', 'local': 'Modèle local',
          'opencode': 'OpenCode', 'openrouter': 'OpenRouter', 'devin': 'Devin', 'antigravity': 'Antigravity',
          'command-code': 'Command Code', 'codebuddy': 'CodeBuddy'}

DEFAULTS = {'stt': {'engine': 'whisper', 'model': '', 'language': 'fr', 'device': 'auto', 'threads': 4, 'phonon_model': 'phonon-2.5'},
            'tts': {'voice': '', 'speed': 1.0, 'volume': 80, 'pocket_temperature': None, 'piper_noise_scale': None, 'piper_noise_w': None},
            'input_device': '', 'output_device': '', 'silence_ms': 1800, 'listen_timeout_s': 0, 'barge_in': False,
            'read_limit': 2500, 'dictation_send': False, 'connector_voices': {}, 'idle_unload_s': 300,
            'runtimes': {}, 'installed': {}, 'samples': []}

WHISPER_REPO, WHISPER_REVISION = 'ggerganov/whisper.cpp', '5359861c739e955e79d9a303bcbc70fb988958b1'
PIPER_REPO, PIPER_REVISION = 'rhasspy/piper-voices', 'c10ece1aade47bb51c153c893d14e5bf8e5b7117'
PIPER_URL = 'https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip'


def _whisper(id, name, file, size, sha, note):
    return {'id': id, 'kind': 'stt_model', 'name': name, 'file': file, 'bytes': size, 'sha256': sha, 'note': note,
            'license': 'MIT', 'source': 'https://huggingface.co/' + WHISPER_REPO, 'revision': WHISPER_REVISION}


CATALOG = [
    {'id': 'phonon-stt', 'kind': 'stt_engine', 'engine': 'phonon', 'name': 'Phonon-2 / Phonon-2.5 · dictée CPU',
     'bytes': 314000000, 'approx': True, 'license': 'Code Apache-2.0 · modèles CC BY 4.0',
     'source': 'https://github.com/fermionresearch/phonon',
     'note': 'Phonon-2 : anglais uniquement. Phonon-2.5 : 25 langues dont le français. Poids ≈ 156–158 Mo chacun ; Python et PyTorch CPU téléchargés en plus. Modèle conservé en RAM entre les dictées. Texte après la phrase, aucun GPU requis.'},
    {'id': 'whisper-runtime-cpu', 'kind': 'stt_runtime', 'name': 'whisper.cpp · processeur', 'backend': 'cpu',
     'asset': 'whisper-bin-x64.zip', 'bytes': 8573270, 'license': 'MIT', 'source': 'https://github.com/ggml-org/whisper.cpp',
     'note': 'Moteur de reconnaissance vocale. Dernière publication Windows x64, empreinte SHA-256 publiée par GitHub.'},
    {'id': 'whisper-runtime-cuda', 'kind': 'stt_runtime', 'name': 'whisper.cpp · NVIDIA CUDA 12.4', 'backend': 'cuda',
     'asset': 'whisper-cublas-12.4.0-bin-x64.zip', 'bytes': 674539285, 'license': 'MIT', 'source': 'https://github.com/ggml-org/whisper.cpp',
     'note': 'Transcription sur carte NVIDIA (pilote compatible CUDA 12.4). Gros téléchargement : bibliothèques CUDA incluses.'},
    _whisper('whisper-tiny', 'Whisper Tiny', 'ggml-tiny.bin', 77691713, 'be07e048e1e599ad46341c8d2a135645097a538221678b7acdd1b1919c6e1b21', 'Très rapide, précision limitée.'),
    _whisper('whisper-base', 'Whisper Base', 'ggml-base.bin', 147951465, '60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe', 'Rapide, correct pour des phrases simples.'),
    _whisper('whisper-small-q5', 'Whisper Small (quantifié q5_1)', 'ggml-small-q5_1.bin', 190085487, 'ae85e4a935d7a567bd102fe55afc16bb595bdb618e11b2fc7591bc08120411bb', 'Presque la précision de Small, 2,5 fois plus léger.'),
    _whisper('whisper-small', 'Whisper Small', 'ggml-small.bin', 487601967, '1be3a9b2063867b937e64e2ec7483364a79917e157fa98c5d94b5c1fffea987b', 'Bon compromis en français ; recommandé pour commencer.'),
    _whisper('whisper-turbo-q5', 'Whisper Large v3 Turbo (q5_0)', 'ggml-large-v3-turbo-q5_0.bin', 574041195, '394221709cd5ad1f40c46e6031ca61bce88931e6e088c188294c6d5a55ffa7e2', 'Très bonne précision, compressé ; lent sans carte graphique.'),
    _whisper('whisper-turbo-q8', 'Whisper Large v3 Turbo (q8_0)', 'ggml-large-v3-turbo-q8_0.bin', 874188075, '317eb69c11673c9de1e1f0d459b253999804ec71ac4c23c17ecf5fbe24e259a1', 'Presque identique au modèle complet, deux fois plus léger. Recommandé avec une carte NVIDIA et le moteur CUDA.'),
    _whisper('whisper-turbo', 'Whisper Large v3 Turbo', 'ggml-large-v3-turbo.bin', 1624555275, '1fc70f774d38eb169993ac391eea357ef47c88757ef72ee5943879b7e8e2bc69', 'Version complète : la meilleure précision de Whisper à une vitesse raisonnable sur carte graphique.'),
    _whisper('whisper-large-v3', 'Whisper Large v3', 'ggml-large-v3.bin', 3095033483, '64d182b440b98d5203c4f9bd541544d84c605196c4f7b845dfa11fb23594d1e2', 'Le plus gros Whisper : un peu plus précis que Turbo, bien plus lent. Carte graphique indispensable.'),
    {'id': 'piper-runtime', 'kind': 'tts_runtime', 'name': 'Piper · moteur de synthèse', 'url': PIPER_URL, 'bytes': 22477236,
     'license': 'MIT', 'source': 'https://github.com/rhasspy/piper/releases/tag/2023.11.14-2',
     'note': 'Dernière version Windows publiée (2023.11.14-2) ; le dépôt est archivé. Aucune empreinte SHA-256 publiée : '
             'celle du fichier reçu est calculée et affichée.'},
    {'id': 'pocket-tts', 'kind': 'tts_engine', 'engine': 'pocket', 'name': 'Pocket TTS · Kyutai (voix naturelles)', 'bytes': 1100000000, 'approx': True,
     'license': 'Code MIT, modèle CC BY 4.0', 'source': 'https://github.com/kyutai-labs/pocket-tts',
     'note': 'Les voix les plus naturelles de la liste : français (« estelle » et 21 autres timbres) et anglais, sur le processeur. '
             'Copie de voix à partir d’un échantillon de quelques secondes (accès au modèle à accepter sur Hugging Face). '
             'Installe un Python 3.12 isolé avec PyTorch pour processeur, puis le modèle français (672 Mo).'},
    {'id': 'kyutai-stt', 'kind': 'stt_engine', 'engine': 'kyutai', 'name': 'Kyutai STT 1B · dictée en direct', 'bytes': 5300000000, 'approx': True,
     'license': 'Code MIT, modèle CC BY 4.0', 'source': 'https://huggingface.co/kyutai/stt-1b-en_fr',
     'note': 'Français et anglais ; les mots s’affichent pendant que vous parlez. Carte graphique NVIDIA recommandée. '
             'Installe un Python 3.12 isolé avec PyTorch CUDA (≈ 2,8 Go) et le modèle (2,4 Go).'},
]
from .voice_expressive import CATALOG as EXPRESSIVE_CATALOG, DEFAULTS as EXPRESSIVE_DEFAULTS, SPECS as EXPRESSIVE_SPECS, SPEAKERS, FISH_STYLES, ExpressiveTTS
CATALOG.extend(EXPRESSIVE_CATALOG)
from .piper_catalog import load as load_piper_catalog
CATALOG.extend(load_piper_catalog())
DEFAULTS['tts'].update(EXPRESSIVE_DEFAULTS)
ITEMS = {item['id']: item for item in CATALOG}


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _extract(archive, destination):
    with zipfile.ZipFile(archive) as z:
        for member in z.infolist():
            path = (destination / member.filename).resolve()
            if not path.is_relative_to(destination.resolve()) or (member.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Archive invalide : chemin hors du dossier d’installation.')
        z.extractall(destination)


class Voice:
    def __init__(self, service, audio=None, engines=None):
        self.service = service
        from .piper_catalog import load
        self.piper_cache = service.store.path.parent / 'piper-catalog.json'
        self.piper_items = load(self.piper_cache)
        if audio is None:
            from .voice_audio import WinAudio
            audio = WinAudio()
        self.audio = audio
        # Tests give their own engines: {'stt': object with transcribe(pcm, language), 'tts': callable(key) -> engine}.
        self.engines = engines or {}
        self.lock = threading.RLock()
        self.wake = threading.Condition(self.lock)
        self.closed = False
        self.phonon = None
        self.windows_pending = False
        self.conversation_id = None
        self.reading, self.read_since, self.talking = False, '', False
        self.capture, self.capture_kind, self.transcribing, self.transcript = None, '', False, None
        self.level = self.floor = 0.0
        self.heard_ms = self.silent_ms = self.total_ms = 0
        self.listen_started = self.last_speech = self.last_activity = 0.0
        self.notice, self.error = '', ''
        self.streams = OrderedDict()   # (mission, step) -> {'items': deque, 'done': bool}; read in this order
        self.segmenters = {}           # (mission, step) -> [Segmenter, last feed time]
        self.missions, self.steps = {}, {}
        self.ready, self.playing, self.generation = deque(), None, 0
        self.stop_event = threading.Event()
        self.synthesizing = False
        self.diagnostics = deque(maxlen=256)
        self.metric_start = time.monotonic()
        self.listen_epoch = 0
        self.barge_ms = 0
        self.tts_cache, self.windows, self.windows_list = {}, None, None
        self.threads, self._ending = [], False
        self.python_envs = Environments(self)
        # Kyutai: the recogniser follows the microphone; audio waits in memory while its model loads.
        self.stream, self.stream_lock, self.stream_live, self.stream_buffer = None, threading.Lock(), False, []
        self.streaming, self.stream_failed, self.capture_rate, self.loading = False, False, 16000, ''
        service.store.listeners.append(self.on_event)

    def measure(self, stage, **details):
        # Operational timings only: no microphone recording, transcript or answer stored here.
        with self.lock:
            self.diagnostics.append({'stage': stage, 'at': now(),
                                     'elapsed_ms': round((time.monotonic() - self.metric_start) * 1000, 1), **details})

    # ----- settings -------------------------------------------------------------------------------------------
    def settings(self):
        saved = self.service.config.get('voice') or {}
        merged = json.loads(json.dumps(DEFAULTS))
        for key, value in saved.items():
            merged[key] = {**merged[key], **value} if isinstance(merged.get(key), dict) and isinstance(value, dict) else value
        return merged

    def persist(self, settings):
        self.service.config['voice'] = settings
        self.service.plugins.persist()

    def folder(self):
        manager = getattr(self.service, 'local_models', None)
        base = manager.folder() if manager else self.service.store.path.parent / 'models'
        return base / 'voice'

    def runtimes_folder(self):
        return self.service.store.path.parent / 'runtimes'

    # ----- engines --------------------------------------------------------------------------------------------
    def stt_status(self, settings=None):
        settings = settings or self.settings()
        if settings['stt'].get('engine') == 'phonon':
            model = settings['stt'].get('phonon_model', 'phonon-2.5')
            if model == 'phonon-2' and settings['stt']['language'] == 'fr':
                return {'ready': False, 'reason': 'Phonon-2 est anglais uniquement : choisissez Phonon-2.5 pour le français.'}
            if self.python_envs.installed('phonon'):
                return {'ready': True, 'model': model, 'runtime': 'phonon-cpu', 'streaming': False}
            return {'ready': False, 'reason': 'Installez Phonon dans les moteurs de dictée ci-dessous.'}
        if settings['stt'].get('engine') == 'kyutai':
            if 'stream' in self.engines or self.python_envs.installed('kyutai'):
                return {'ready': True, 'model': 'kyutai-stt', 'runtime': 'kyutai', 'streaming': True}
            return {'ready': False, 'reason': 'Installez Kyutai STT dans Paramètres › Voix, ou choisissez Whisper.'}
        if 'stt' in self.engines:
            return {'ready': True, 'model': 'test', 'runtime': 'test'}
        runtimes = settings['runtimes']
        runtime = next((r for b, r in runtimes.items() if b in ('whisper-cpu', 'whisper-cuda') and Path(r.get('path', '')).is_file()), None)
        installed = [i for i in CATALOG if i['kind'] == 'stt_model' and Path(settings['installed'].get(i['id'], {}).get('path', '')).is_file()]
        chosen = next((i for i in installed if i['id'] == settings['stt']['model']), None) or (installed[-1] if installed and not settings['stt']['model'] else None)
        if not runtime:
            return {'ready': False, 'reason': 'Installez le moteur whisper.cpp dans Paramètres › Voix.'}
        if not chosen:
            return {'ready': False, 'reason': 'Téléchargez un modèle Whisper dans Paramètres › Voix.'}
        return {'ready': True, 'model': chosen['id'], 'runtime': 'cuda' if 'whisper-cuda' in runtimes else 'cpu'}

    def _stt(self, settings):
        if 'stt' in self.engines:
            return self.engines['stt']
        if settings['stt'].get('engine') == 'phonon':
            from .voice_phonon import PhononSTT
            status = self.stt_status(settings)
            if not status['ready']: raise ValueError(status['reason'])
            if self.phonon and self.phonon.model != status['model']:
                self.phonon.close()
                self.phonon = None
            if not self.phonon: self.phonon = PhononSTT(self.python_envs, status['model'])
            return self.phonon
        from .voice_backends import WhisperCpp
        status = self.stt_status(settings)
        if not status['ready']:
            raise ValueError(status['reason'])
        runtimes, device = settings['runtimes'], settings['stt']['device']
        cuda, cpu = runtimes.get('whisper-cuda', {}), runtimes.get('whisper-cpu', {})
        gpu = device == 'gpu' or (device == 'auto' and bool(cuda) and not self._local_model_on_gpu())
        if device == 'gpu' and not Path(cuda.get('path', '')).is_file():
            raise ValueError('Installez whisper.cpp CUDA pour transcrire sur la carte graphique.')
        runtime = cuda if gpu or not Path(cpu.get('path', '')).is_file() else cpu
        return WhisperCpp(runtime['path'], settings['installed'][status['model']]['path'], settings['stt']['threads'], gpu)

    def _local_model_on_gpu(self):
        """The VRAM belongs first to the local model already loaded: the voice then works on the processor."""
        manager = getattr(self.service, 'local_models', None)
        if not manager or not manager.loaded:
            return False
        model = next((m for m in manager.config.get('models', []) if m['id'] == manager.loaded), {})
        return {**manager.config, **model.get('settings', {})}.get('device', 'cpu') != 'cpu'

    def voices(self, refresh=False):
        """Voices you can hear now: those of Windows, and the Piper voices downloaded."""
        settings = self.settings()
        found = []
        if 'tts' in self.engines:
            found.append({'key': 'test:voix', 'name': 'Voix de test', 'language': 'fr-FR', 'backend': 'test'})
        else:
            if self.windows_list is None or refresh:
                try:
                    self.windows_list = self._windows().voices()
                except Exception as exc:
                    self.windows_list = []
                    self.error = 'Voix Windows indisponibles : ' + str(exc)
            found += [{'key': 'windows:' + v['name'], 'name': v['name'], 'language': v['language'], 'backend': 'Windows'} for v in self.windows_list]
        if 'pocket' in self.engines or self.python_envs.installed('pocket'):
            for language, label in POCKET_LANGUAGES.items():
                french = language.startswith('french')
                for name in POCKET_VOICES if french else POCKET_VOICES[1:]:
                    found.append({'key': f'pocket:{language}:{name}', 'name': name.replace('_', ' ').title() + ' · ' + label.lower(),
                                  'language': 'fr-FR' if french else 'en-US', 'backend': 'Pocket TTS'})
                for sample in settings['samples']:
                    found.append({'key': f'pocket:{language}:clone:{sample["id"]}', 'name': sample['name'] + ' (voix copiée) · ' + label.lower(),
                                  'language': 'fr-FR' if french else 'en-US', 'backend': 'Pocket TTS', 'cloned': True})
        for engine in EXPRESSIVE_SPECS:
            if not self.python_envs.installed(engine): continue
            label = {'qwen':'Qwen3-TTS', 'chatterbox':'Chatterbox Multilingual', 'fish':'Fish S2 Pro'}[engine]
            choices = [('custom:'+n, n+' · style dirigé') for n in SPEAKERS] + [('design','Créer une voix par description')] if engine=='qwen' else [('default','Voix du modèle')]
            choices += [('clone:'+sample['id'],sample['name']+' · référence') for sample in settings['samples']]
            for choice,name in choices:
                found.append({'key':engine+':'+choice,'name':name,'language':'fr-FR / en-US','backend':label})
        piper = Path(settings['runtimes'].get('piper', {}).get('path', ''))
        for item in self.catalog_items():
            if item['kind'] == 'tts_voice' and Path(settings['installed'].get(item['id'], {}).get('path', '')).is_file():
                speakers = [(name, str(number)) for name, number in item['speakers'].items()] if item['num_speakers'] > 1 else [('', '')]
                for speaker_name, speaker in speakers:
                    found.append({'key': 'piper:' + item['id'] + (':' + speaker if speaker else ''),
                                  'name': item['name'] + (' · ' + speaker_name if speaker else ''),
                                  'language': item['language'].replace('_', '-'), 'backend': 'Piper',
                                  'available': piper.is_file()})
        from .model_memory import hardware, estimate
        hw = hardware()
        return [{**v, 'memory': estimate(v['key'], hw)} for v in found]

    def resolve_voice(self, connector=None, settings=None):
        """Voice of an agent's answer: the one chosen for its connector, then the general one, then a voice in the
        language of the dictation."""
        settings = settings or self.settings()
        chosen = settings['connector_voices'].get(connector or '') or settings['tts']['voice']
        if chosen:
            return chosen
        voices = [v for v in self.voices() if v.get('available', True)]
        language = settings['stt']['language'] if settings['stt']['language'] != 'auto' else 'fr'
        preferred = [v for v in voices if v['language'].lower().startswith(language)]
        best = next((v for v in preferred if v['backend'] == 'Pocket TTS' and not v.get('cloned')), None) \
            or next((v for v in preferred if v['backend'] == 'Piper'), None) or (preferred or voices or [None])[0]
        if not best:
            raise ValueError('Aucune voix disponible : ajoutez une voix Windows ou téléchargez une voix Piper.')
        return best['key']

    def _windows(self):
        if not self.windows:
            from .voice_backends import WindowsVoices
            self.windows = WindowsVoices()
        return self.windows

    def _synthesize(self, text, key, on_audio=None, cancelled=None):
        settings = self.settings()
        speed = float(settings['tts']['speed'])
        if 'tts' in self.engines:
            return self.engines['tts'](key).synthesize(text)
        backend, _, rest = key.partition(':')
        if backend in EXPRESSIVE_SPECS:
            variant, _, value = rest.partition(':')
            options = {'variant':variant, 'language': 'en' if settings['stt']['language']=='en' else 'fr'}
            if variant=='clone':
                sample = next((s for s in settings['samples'] if s['id']==value), None)
                if not sample or not Path(sample['file']).is_file(): raise ValueError('Échantillon de référence absent.')
                options.update(reference=sample['file'], reference_text=sample.get('text',''))
                if backend=='fish' and not sample.get('text','').strip(): raise ValueError('Fish demande la transcription de votre échantillon : renseignez-la dans Mes voix.')
            tts=settings['tts']
            if backend=='qwen':
                options.update(instruct=tts['qwen_instruct'], speaker=value)
                if variant=='design' and not options['instruct'].strip(): raise ValueError('Décrivez la voix Qwen dans Paramètres > Voix, puis enregistrez.')
            elif backend=='chatterbox': options.update(exaggeration=tts['chatterbox_exaggeration'], cfg=tts['chatterbox_cfg'], temperature=tts['chatterbox_temperature'])
            else: options.update(style=tts['fish_style'], temperature=tts['fish_temperature'], top_p=tts['fish_top_p'])
            # Keep only one expressive engine in VRAM. Other application models are untouched.
            for old in [k for k in self.tts_cache if k[0] in EXPRESSIVE_SPECS and k!=(backend,variant)]:
                self.tts_cache.pop(old).close()
            engine=self.tts_cache.get((backend,variant))
            if not engine: engine=self.tts_cache[(backend,variant)]=ExpressiveTTS(self.python_envs,backend)
            if on_audio: return engine.synthesize_stream(text,options,on_audio,cancelled)
            return engine.synthesize(text,options)
        if backend == 'windows':
            return self._windows().synthesize(text, rest, speed)
        if backend == 'pocket':
            language, _, voice = rest.partition(':')
            if voice.startswith('clone:'):
                sample = next((s for s in settings['samples'] if s['id'] == voice[6:]), None)
                if not sample or not Path(sample['file']).is_file():
                    raise ValueError('Échantillon de voix absent : recréez la voix dans Paramètres › Voix.')
                voice = sample['file']
            engine = self.tts_cache.get(('pocket', language))
            if not engine:
                engine = self.tts_cache[('pocket', language)] = self.engines['pocket'](language) if 'pocket' in self.engines \
                    else PocketTTS(self.python_envs, language)
            options = {'temperature': settings['tts'].get('pocket_temperature')} if isinstance(engine, PocketTTS) else {}
            if on_audio and hasattr(engine, 'synthesize_stream'):
                return engine.synthesize_stream(text, voice, on_audio, cancelled, **options)
            return engine.synthesize(text, voice, **options)
        if backend == 'piper':
            item_id, _, speaker = rest.partition(':')
            installed = settings['installed'].get(item_id, {})
            runtime = settings['runtimes'].get('piper', {}).get('path', '')
            if not installed or not Path(installed.get('path', '')).is_file():
                raise ValueError('Voix Piper absente : téléchargez-la dans Paramètres › Voix.')
            noise_scale, noise_w = settings['tts'].get('piper_noise_scale'), settings['tts'].get('piper_noise_w')
            cache = (key, speed, noise_scale, noise_w)
            if cache not in self.tts_cache:
                from .voice_backends import Piper
                for old in [k for k in self.tts_cache if k[0].startswith('piper:')]:
                    self.tts_cache.pop(old).close()
                self.tts_cache[cache] = Piper(runtime, installed['path'], speaker or None, speed, noise_scale, noise_w)
            return self.tts_cache[cache].synthesize(text)
        raise ValueError('Voix inconnue : ' + key)

    # ----- reading answers ------------------------------------------------------------------------------------
    def on_event(self, mission_id, step_id, kind, data):
        """Called for every event CyAI records. Only the answers of the conversation being read concern it."""
        if not self.reading or self.closed or not mission_id:
            return
        try:
            info = self.missions.get(mission_id)
            if info is None:
                rows = self.service.store.rows('SELECT conversation_id,created_at,spec FROM missions WHERE id=?', (mission_id,))
                if not rows:
                    return
                spec = json.loads(rows[0]['spec'] or '{}')
                info = {'read': rows[0]['conversation_id'] == self.conversation_id and rows[0]['created_at'] >= self.read_since,
                        'planning': bool(spec.get('planning'))}
                self.missions[mission_id] = info
            if not info['read']:
                return
            if not info.get('observed'):
                info['observed'] = True
                self.measure('mission_event', mission_id=mission_id)
            if kind == 'delta' and not info.get('first_delta'):
                info['first_delta'] = True
                self.measure('first_text', mission_id=mission_id)
            if kind == 'step_completed':
                self.measure('text_complete', mission_id=mission_id, step_id=step_id)
            if kind == 'cancel_requested':
                with self.wake:
                    info['read'] = False
                    for key in [k for k in self.streams if k[0] == mission_id]:
                        self.streams.pop(key)
                    self.segmenters = {k: v for k, v in self.segmenters.items() if k[0] != mission_id}
                    self.ready = deque(r for r in self.ready if r['mission'] != mission_id)
                    if self.playing and self.playing['mission'] == mission_id:
                        self.stop_event.set()
                    self.wake.notify_all()
                return
            if kind == 'approval_requested':
                self.say_notice('Une autorisation est demandée dans la conversation.', mission_id)
                return
            if not step_id or kind not in ('delta', 'step_completed', 'error'):
                return
            step = self.steps.get(step_id)
            if step is None:
                row = self.service.store.one('SELECT connector,model,name FROM steps WHERE id=?', (step_id,))
                connector = self.service.engine.connectors.get(row['connector'])
                streamed = getattr(connector, 'speech_deltas', row['connector'] in STREAMED) and not info['planning']
                step = self.steps[step_id] = {**row, 'streamed': streamed}
            final = None
            if kind == 'step_completed' and not step['streamed']:
                rows = self.service.store.rows("SELECT content FROM messages WHERE source_id=? AND role='assistant' ORDER BY seq DESC LIMIT 1", (step_id,))
                final = rows[0]['content'] if rows else ''
            self._take(mission_id, step_id, kind, data, step, final, info)
        except Exception as exc:
            self.error = 'Lecture vocale : ' + str(exc)

    def _take(self, mission_id, step_id, kind, data, step, final, info):
        key = (mission_id, step_id)
        settings = self.settings()
        with self.wake:
            entry = self.segmenters.setdefault(key, [Segmenter(int(settings['read_limit'])), time.monotonic()])
            segmenter = entry[0]
            if kind == 'delta' and step['streamed']:
                entry[1] = time.monotonic()
                self._add(key, segmenter.feed(str(data.get('text', ''))), step, settings)
                return
            if final is not None:
                text, plan = planning_reply(final) if info['planning'] else (final, False)
                self._add(key, segmenter.feed(text), step, settings)
            self._add(key, segmenter.flush(), step, settings)
            if segmenter.truncated:
                self._add(key, ['La suite est dans la conversation.'], step, settings)
            if final is not None and info['planning'] and plan:
                self._add(key, ['Le plan attend votre autorisation dans la conversation.'], step, settings)
            if kind == 'error' and data.get('status') == 'failed':
                self._add(key, ['La réponse s’est arrêtée sur une erreur.'], step, settings)
            self._finish(key)

    def _add(self, key, segments, step, settings):
        if not segments:
            return
        stream = self.streams.setdefault(key, {'items': deque(), 'done': False})
        voice = self.resolve_voice(step.get('connector'), settings)
        for text in segments:
            stream['items'].append({'text': text, 'voice': voice, 'label': AGENTS.get(step.get('connector'), step.get('connector') or 'CyAI'), 'mission': key[0]})
        self.last_activity = time.monotonic()
        self._start_threads()
        self.wake.notify_all()

    def _finish(self, key):
        self.segmenters.pop(key, None)
        if key in self.streams:
            self.streams[key]['done'] = True
        self.wake.notify_all()

    def say_notice(self, text, mission=None):
        with self.wake:
            key = ('notice', uid())
            self._add(key, [text], {'connector': None}, self.settings())
            self.streams[key]['items'][-1]['mission'] = mission
            self._finish(key)

    def speak(self, text, connector=None, voice=None):
        """Reads a text now, at the user's request (a message, a test of the voice)."""
        settings = self.settings()
        segments, truncated = speakable(text, int(settings['read_limit']))
        if truncated:
            segments.append('La suite est dans la conversation.')
        if not segments:
            raise ValueError('Rien à lire dans ce texte.')
        with self.wake:
            key = ('manual', uid())
            step = {'connector': connector}
            if voice:
                self.streams[key] = {'items': deque({'text': s, 'voice': voice, 'label': 'CyAI', 'mission': None} for s in segments), 'done': True}
                self._start_threads()
                self.wake.notify_all()
            else:
                self._add(key, segments, step, settings)
            self._finish(key)
        return {'segments': len(segments)}

    def _next_item(self):
        for key, stream in list(self.streams.items()):
            if stream['items']:
                return stream['items'].popleft()
            if stream['done']:
                del self.streams[key]
                continue
            return None  # This agent is still writing: the next one waits its turn, voices never overlap.
        return None

    def _synthesis_loop(self):
        while not self.closed:
            with self.wake:
                item = None
                while not self.closed:
                    if len(self.ready) < 2:
                        item = self._next_item()
                        if item:
                            break
                    self.wake.wait(.1)
                if self.closed:
                    return
                generation = self.generation
                self.synthesizing = True
            began = time.monotonic()
            self.measure('tts_start', characters=len(item['text']), mission_id=item.get('mission'))
            streaming = item['voice'].split(':')[0] in ('pocket', *EXPRESSIVE_SPECS) and hasattr(self.audio, 'play_chunks')
            chunked = {**item, 'chunks': queue.Queue(maxsize=8), 'done': threading.Event()}
            sent = False
            def cancelled():
                return self.closed or generation != self.generation
            def on_audio(wav):
                nonlocal sent
                if cancelled():
                    return
                if not sent:
                    self.measure('tts_first_audio', duration_ms=round((time.monotonic()-began)*1000, 1))
                    with self.wake:
                        if cancelled():
                            return
                        self.ready.append(chunked)
                        self.wake.notify_all()
                    sent = True
                while not cancelled():
                    try:
                        chunked['chunks'].put(wav, timeout=.05)
                        return
                    except queue.Full:
                        pass
            try:
                wav = self._synthesize(item['text'], item['voice'], on_audio, cancelled) if streaming else self._synthesize(item['text'], item['voice'])
                with self.wake:
                    if wav is not None and not cancelled():
                        self.ready.append({**item, 'wav': wav})
                        self.wake.notify_all()
            except Exception as exc:
                self.error = 'Synthèse vocale : ' + str(exc)
            finally:
                chunked['done'].set()
                with self.wake:
                    self.synthesizing = False
                    self.measure('tts_complete', duration_ms=round((time.monotonic()-began)*1000, 1))
                    self.wake.notify_all()

    def _play_loop(self):
        while not self.closed:
            with self.wake:
                while not self.closed and not self.ready:
                    self.wake.wait(.5)
                if self.closed:
                    return
                item = self.ready.popleft()
                self.playing = item
                self.stop_event.clear()
            settings = self.settings()
            try:
                self.measure('playback_start', mission_id=item.get('mission'))
                if 'chunks' in item:
                    self.audio.play_chunks(item['chunks'], item['done'], settings['output_device'], int(settings['tts']['volume']), self.stop_event)
                else:
                    self.audio.play(item['wav'], settings['output_device'], int(settings['tts']['volume']), self.stop_event)
            except Exception as exc:
                self.error = 'Lecture audio : ' + str(exc)
                self.stop_speaking()
            finally:
                with self.wake:
                    self.measure('playback_stopped' if self.stop_event.is_set() else 'playback_complete')
                    self.playing = None
                    self.last_activity = time.monotonic()
                    self.wake.notify_all()

    def speaking(self):
        return bool(self.synthesizing or self.playing or self.ready or any(s['items'] for s in self.streams.values()))

    def stop_speaking(self):
        """« Arrêter la voix » : silence now, the rest of the answers in progress is not read. The agents keep
        working: cancelling an answer is another button."""
        with self.wake:
            self.measure('interrupt_requested')
            self.generation += 1
            self.streams.clear()
            self.ready.clear()
            self.segmenters.clear()
            for info in self.missions.values():
                info['read'] = False
            self.stop_event.set()
            self.wake.notify_all()

    # ----- listening ------------------------------------------------------------------------------------------
    def listen(self, conversation_id, kind):
        settings = self.settings()
        status = self.stt_status(settings)
        if not status['ready']:
            raise ValueError(status['reason'])
        streaming = bool(status.get('streaming'))
        with self.wake:
            if self.capture:
                return
            if self.transcribing:
                raise ValueError('La transcription en cours doit se terminer avant une nouvelle écoute.')
            self.listen_epoch += 1
            self.barge_ms = 0
            self.heard_ms = self.silent_ms = self.total_ms = 0
            self.level, self.floor = 0.0, .2
            self.listen_started = self.last_speech = time.monotonic()
            self.notice = self.error = ''
            with self.stream_lock:
                self.streaming, self.stream_live, self.stream_failed, self.stream_buffer = streaming, False, False, []
            self.capture_rate = KyutaiSTT.RATE if streaming else 16000
            try:
                self.capture = self.audio.open_input(settings['input_device'], self._chunk, self.capture_rate)
                self.capture.retain = False
            except OSError as exc:
                raise ValueError(str(exc))
            self.measure('listen_start', mode=kind)
            self.capture_kind = kind
            self._start_threads()
        if streaming:
            threading.Thread(target=self._start_stream, args=(settings,), daemon=True).start()

    def _stream_device(self, settings):
        device = settings['stt']['device']
        return 'cpu' if device == 'cpu' or (device == 'auto' and self._local_model_on_gpu()) else device

    def _start_stream(self, settings):
        try:
            if not self.stream or not self.stream.alive():
                self.loading = 'Chargement de la dictée Kyutai… La première fois, cela peut prendre une minute.'
                self.stream = self.engines['stream']() if 'stream' in self.engines else KyutaiSTT(self.python_envs, self._stream_device(settings))
            self.stream.begin()
            while True:  # What was said while the model loaded goes first, in order.
                with self.stream_lock:
                    if not self.stream_buffer:
                        self.stream_live = True
                        break
                    batch, self.stream_buffer = self.stream_buffer, []
                for pcm in batch:
                    self.stream.feed(pcm)
        except Exception as exc:
            self.stream_failed = True
            self.error = 'Dictée Kyutai : ' + str(exc)
        finally:
            self.loading = ''

    def _chunk(self, pcm):
        from .voice_audio import level
        settings = self.settings()
        if self.streaming:
            with self.stream_lock:
                live = self.stream_live
                if not live:
                    self.stream_buffer.append(pcm)
            if live:
                try:
                    self.stream.feed(pcm)
                except Exception as exc:
                    self.error = 'Dictée Kyutai : ' + str(exc)
        loud, ms = level(pcm), len(pcm) * 1000 // (self.capture_rate * 2)
        self.level = loud
        # Never learn speech as background noise: that made sustained speech become silence.
        speech = loud > max(self.floor + .15, .3)
        if not speech:
            self.floor = loud if loud < self.floor else self.floor + (loud - self.floor) * .01
        if self.capture:
            self.capture.retain = not self.streaming and (speech or self.heard_ms > 0)
        self.total_ms += ms
        if speech:
            if not self.heard_ms:
                self.measure('speech_start')
            self.heard_ms += ms
            self.barge_ms += ms
            if settings.get('barge_in') and self.talking and self.barge_ms >= 150 and self.speaking() and not self.stop_event.is_set():
                self.stop_speaking()
            self.silent_ms = 0
            self.last_speech = time.monotonic()
        else:
            self.barge_ms = 0
            if self.heard_ms >= 200:
                self.silent_ms += ms
        # In a voice conversation, a silence after speech ends the sentence; a dictation ends on your click.
        end = self.capture_kind == 'conversation' and self.heard_ms >= 300 and self.silent_ms >= int(settings['silence_ms'])
        if end and not getattr(self, '_ending', False):
            self.measure('end_of_speech', silence_ms=self.silent_ms, audio_ms=self.total_ms)
            self._ending = True
            threading.Thread(target=self.finish_listening, daemon=True).start()

    def finish_listening(self, transcribe=True):
        with self.wake:
            capture, kind, heard = self.capture, self.capture_kind, self.heard_ms
            if not capture:
                return
            self.capture, self.level = None, 0.0
            self.transcribing = transcribe
            epoch, conversation = self.listen_epoch, self.conversation_id
        started = time.monotonic()
        self.measure('transcription_start')
        pcm = capture.stop()
        self._ending = False
        text = ''
        try:
            if self.streaming:
                deadline = time.monotonic() + 600
                while not self.stream_live and not self.stream_failed and time.monotonic() < deadline:
                    time.sleep(.05)
                final = self.stream.finish() if self.stream_live else ''
                if transcribe and heard >= 250:
                    text = usable_transcript(final)
            elif transcribe and heard >= 250:
                settings = self.settings()
                text = usable_transcript(self._stt(settings).transcribe(pcm, settings['stt']['language']))
        except Exception as exc:
            self.error = 'Transcription : ' + str(exc)
        finally:
            del pcm  # The recording is never kept.
            with self.wake:
                self.transcribing = False
                with self.stream_lock:
                    self.streaming = self.stream_live = False
                self.last_activity = time.monotonic()
                self.measure('transcription_complete', duration_ms=round((time.monotonic()-started)*1000, 1))
                if text and epoch == self.listen_epoch and conversation == self.conversation_id:
                    self.transcript = {'id': uid(), 'text': text, 'conversation_id': self.conversation_id,
                                       'send': kind == 'conversation' or bool(self.settings()['dictation_send']), 'at': time.monotonic()}
                elif transcribe and not self.error:
                    self.notice = 'Rien entendu.' if heard < 250 else 'Rien de compréhensible.'
                self.wake.notify_all()

    # ----- modes ----------------------------------------------------------------------------------------------
    def _bind(self, conversation_id):
        self.service.conversation(conversation_id)
        if self.conversation_id and self.conversation_id != conversation_id:
            self.off()
        self.conversation_id = conversation_id

    def set_reading(self, conversation_id, on):
        with self.wake:
            if on:
                if not self.reading:
                    self.read_since = now()
                self._bind(conversation_id)
                self.reading = True
            else:
                self.reading = self.talking = False
                self.stop_speaking()
        self._start_threads()

    def set_talking(self, conversation_id, on):
        if not on:
            with self.wake:
                self.talking = False
                self.listen_epoch += 1
            if self.capture and self.capture_kind == 'conversation':
                self.finish_listening(False)
            return
        status = self.stt_status()
        if not status['ready']:
            raise ValueError(status['reason'])
        self.set_reading(conversation_id, True)
        self.listen(conversation_id, 'conversation')
        with self.wake:
            self.talking = True

    def off(self):
        """Everything off: the microphone closes, the voice stops, nothing is read any more."""
        with self.wake:
            self.listen_epoch += 1
            self.talking = self.reading = False
            self.transcript = None
            self.conversation_id = None
        if self.capture:
            self.finish_listening(False)
        self.stop_speaking()

    # ----- housekeeping ---------------------------------------------------------------------------------------
    def _start_threads(self):
        if self.threads:
            return
        for target in (self._synthesis_loop, self._play_loop, self._monitor_loop):
            thread = threading.Thread(target=target, daemon=True)
            thread.start()
            self.threads.append(thread)

    def busy(self, conversation_id):
        if not conversation_id:
            return None
        rows = self.service.store.rows(f"SELECT id,status FROM missions WHERE conversation_id=? AND status IN ({','.join('?' * len(BUSY))}) ORDER BY created_at DESC",
                                       (conversation_id, *BUSY))
        return rows[0] if rows else None

    def _monitor_loop(self):
        while not self.closed:
            time.sleep(.15)
            try:
                self._tick()
            except Exception as exc:
                self.error = 'Voix : ' + str(exc)

    def _tick(self):
        conversation = self.conversation_id
        busy = self.busy(conversation)  # Read before taking the voice lock: the database lock always comes first.
        active = {r['id'] for r in self.service.store.rows(f"SELECT id FROM missions WHERE status IN ({','.join('?' * len(BUSY))})", BUSY)} if self.segmenters else set()
        settings = self.settings()
        with self.wake:
            moment = time.monotonic()
            for key, (segmenter, fed) in list(self.segmenters.items()):
                if key[0] not in active and moment - fed > 2:
                    self._add(key, segmenter.flush(), self.steps.get(key[1], {}), settings)
                    self._finish(key)
                elif moment - fed > 1.2:
                    self._add(key, segmenter.idle(), self.steps.get(key[1], {}), settings)
            if self.transcript and busy:
                self.transcript['at'] = moment  # A dictation waiting for the current answer is not forgotten.
            if self.transcript and moment - self.transcript['at'] > 90:
                # The page did not take the transcript (closed?): nothing is sent behind your back.
                self.transcript, self.talking = None, False
                self.notice = 'Conversation vocale arrêtée : la page n’a pas repris la dictée.'
            listen = (self.talking and not self.capture and not self.transcribing and not self.transcript and (settings.get('barge_in') or (not busy and not self.speaking())) and moment - self.last_activity > .15)
            timeout = int(settings['listen_timeout_s']) > 0 and self.capture and self.capture_kind == 'conversation' and \
                moment - max(self.listen_started, self.last_speech) > int(settings['listen_timeout_s'])
        if timeout:
            with self.wake:
                self.talking = False
            self.finish_listening(False)
            self.notice = 'Conversation vocale arrêtée : aucune parole depuis %d secondes. Le micro est fermé.' % int(settings['listen_timeout_s'])
        elif listen:
            try:
                self.listen(conversation, 'conversation')
            except ValueError as exc:
                with self.wake:
                    self.talking = False
                self.error = str(exc)
        for key, engine in list(self.tts_cache.items()):
            idle = engine.idle_for()
            if idle is not None and idle > int(settings['idle_unload_s']):
                self.tts_cache.pop(key).close()
        if self.windows and (self.windows.idle_for() or 0) > int(settings['idle_unload_s']):
            self.windows.close()
        if self.phonon and not self.capture and not self.transcribing and self.phonon.idle_for() > int(settings['idle_unload_s']):
            self.phonon.close()
            self.phonon = None
        if self.stream and not self.capture and not self.transcribing and self.stream.idle_for() > int(settings['idle_unload_s']):
            self.stream.close()  # The recogniser gives its memory (and VRAM) back when you stop dictating.
            self.stream = None

    def shutdown(self):
        self.closed = True
        if self.phonon: self.phonon.close()
        if self.capture:
            self.capture.stop()
            self.capture = None
        self.stop_event.set()
        with self.wake:
            self.wake.notify_all()
        for engine in self.tts_cache.values():
            engine.close()
        if self.windows:
            self.windows.close()
        if self.stream:
            self.stream.close()

    # ----- state ----------------------------------------------------------------------------------------------
    def state(self):
        busy = self.busy(self.conversation_id)
        settings = self.settings()
        with self.wake:
            phase = ('listening' if self.capture else 'transcribing' if self.transcribing else 'pending' if self.transcript
                     else 'speaking' if self.speaking() else 'approval' if busy and busy['status'] == 'awaiting_approval'
                     else 'thinking' if busy else 'idle')
            return {'conversation_id': self.conversation_id, 'phase': phase, 'microphone_open': bool(self.capture),
                    'listening_for': self.capture_kind if self.capture else '', 'level': round(self.level, 3),
                    'heard': self.heard_ms >= 250, 'reading': self.reading, 'talking': self.talking,
                    'speaking': (self.playing or {}).get('label', '') if self.playing else '',
                    'transcript': {k: v for k, v in self.transcript.items() if k != 'at'} if self.transcript else None,
                    'busy_mission': busy['id'] if busy else None, 'notice': self.notice, 'error': self.error,
                    'partial': (getattr(self.stream, 'partial', '') if self.streaming and self.stream_live else ''),
                    'loading': self.loading, 'diagnostics': list(self.diagnostics), 'barge_in': settings.get('barge_in', False),
                    'stt': self.stt_status(settings)}

    # ----- models ---------------------------------------------------------------------------------------------
    def catalog_items(self):
        return [i for i in CATALOG if i['kind'] != 'tts_voice'] + self.piper_items

    def catalog(self):
        settings = self.settings()
        items = []
        for item in self.catalog_items():
            record = settings['runtimes'].get({'stt_runtime': 'whisper-' + item.get('backend', ''), 'tts_runtime': 'piper'}.get(item['kind'], ''), {}) \
                if item['kind'].endswith('runtime') else settings['installed'].get(item['id'], {})
            if item['kind'] in ('tts_engine', 'stt_engine'):
                record = self.python_envs.record(item['engine'])
                installed = self.python_envs.installed(item['engine'])
            else:
                installed = bool(record) and Path(record.get('path', '')).is_file()
            items.append({**item, 'installed': installed, 'record': record if installed else None,
                          'in_use': installed and (settings['stt']['model'] == item['id'] or settings['tts']['voice'].startswith('piper:' + item['id'])
                                                   or (item.get('engine') in ('kyutai', 'phonon') and settings['stt']['engine'] == item.get('engine'))
                                                   or (item.get('engine') in ('pocket', *EXPRESSIVE_SPECS) and settings['tts']['voice'].startswith(item['engine']+':')))})
        jobs = getattr(getattr(self.service, 'local_models', None), 'jobs', {})
        return {'items': items, 'folder': str(self.folder()), 'runtimes_folder': str(self.runtimes_folder()),
                'jobs': [j for j in jobs.values() if j['name'].startswith('Voix · ')]}

    def install(self, item_id):
        item = next((i for i in self.catalog_items() if i['id'] == item_id), None)
        if not item:
            raise ValueError('Élément vocal inconnu.')
        manager = getattr(self.service, 'local_models', None)
        if not manager:
            raise ValueError('Le gestionnaire de téléchargements n’est pas disponible.')
        from .local_models import download
        if item['kind'] in ('tts_engine', 'stt_engine'):
            return manager.job('Voix · ' + item['name'], lambda progress: self.python_envs.install(item['engine'], progress))

        def fetch(url, target, progress, sha):
            if target.exists():
                if sha and _sha256(target) == sha:
                    return sha  # Already there and intact: nothing to download again.
                raise ValueError('Un fichier existe déjà à cet emplacement : ' + str(target))
            return download(url, target, progress, sha)

        def run(progress):
            settings = self.settings()
            if item['kind'] == 'stt_runtime':
                from .connectors import request_json
                releases = request_json('https://api.github.com/repos/ggml-org/whisper.cpp/releases?per_page=10', headers={'User-Agent': 'CyAI'})
                release = next((r for r in releases if any(a['name'] == item['asset'] for a in r['assets'])), None)
                if not release:
                    raise ValueError('Aucune publication whisper.cpp ne fournit ' + item['asset'] + '.')
                asset = next(a for a in release['assets'] if a['name'] == item['asset'])
                if not asset.get('digest', '').startswith('sha256:'):
                    raise ValueError('La publication ne fournit pas de SHA-256 vérifiable.')
                destination = self.runtimes_folder() / ('whisper-' + release['tag_name'] + '-' + item['backend'] + '-' + uid()[:8])
                destination.mkdir(parents=True)
                archive = destination / asset['name']
                sha = download(asset['browser_download_url'], archive, progress, asset['digest'])
                _extract(archive, destination)
                archive.unlink()
                executable = next(destination.rglob('whisper-cli.exe'), None) or next(destination.rglob('main.exe'), None)
                if not executable:
                    raise ValueError('whisper-cli.exe absent de la publication.')
                record = {'path': str(executable), 'folder': str(destination), 'version': release['tag_name'], 'sha256': sha, 'published_sha': True}
                settings['runtimes']['whisper-' + item['backend']] = record
            elif item['kind'] == 'tts_runtime':
                destination = self.runtimes_folder() / ('piper-2023.11.14-2-' + uid()[:8])
                destination.mkdir(parents=True)
                archive = destination / 'piper_windows_amd64.zip'
                sha = download(item['url'], archive, progress)
                _extract(archive, destination)
                archive.unlink()
                executable = next(destination.rglob('piper.exe'), None)
                if not executable:
                    raise ValueError('piper.exe absent de l’archive.')
                settings['runtimes']['piper'] = {'path': str(executable), 'folder': str(destination), 'version': '2023.11.14-2',
                                                 'sha256': sha, 'published_sha': False}
            else:
                repo, revision = (WHISPER_REPO, WHISPER_REVISION) if item['kind'] == 'stt_model' else (PIPER_REPO, item['revision'])
                base = 'https://huggingface.co/' + repo + '/resolve/' + revision + '/'
                if item['kind'] == 'stt_model':
                    target = self.folder() / 'whisper' / item['file']
                    sha = fetch(base + item['file'], target, progress, item['sha256'])
                else:
                    target = self.folder() / 'piper' / item['id'] / (item['id'] + '.onnx')
                    from .piper_catalog import verify_md5
                    if target.exists():
                        verify_md5(target, item['md5'])
                        sha = _sha256(target)
                    else:
                        sha = fetch(base + urllib.parse.quote(item['file']), target, progress, item['sha256'])
                        try: verify_md5(target, item['md5'])
                        except ValueError:
                            target.unlink(missing_ok=True)
                            raise
                    config = target.with_name(target.name + '.json')
                    if not config.exists():
                        download(base + urllib.parse.quote(item['file'] + '.json'), config, lambda *_: None)
                    try: verify_md5(config, item['config_md5'])
                    except ValueError:
                        config.unlink(missing_ok=True)
                        raise
                settings['installed'][item['id']] = {'path': str(target), 'sha256': sha, 'bytes': target.stat().st_size, 'revision': revision}
            self.persist(settings)

        return manager.job('Voix · ' + item['name'], run)

    def verify(self, item_id):
        item = next((i for i in self.catalog_items() if i['id'] == item_id), None)
        if item and item['kind'] in ('tts_engine', 'stt_engine'):
            return self.python_envs.verify(item['engine'])
        settings = self.settings()
        record = settings['runtimes'].get('whisper-' + item.get('backend', '') if item and item['kind'] == 'stt_runtime' else 'piper', {}) \
            if item and item['kind'].endswith('runtime') else settings['installed'].get(item_id, {})
        if not item or not record:
            raise ValueError('Élément non installé.')
        path = Path(record['path'])
        if item['kind'].endswith('runtime'):
            return {'ok': path.is_file(), 'detail': 'Moteur présent.' if path.is_file() else 'Moteur absent : réinstallez-le.',
                    'sha256': record.get('sha256', ''), 'published': record.get('published_sha', False)}
        if not path.is_file():
            return {'ok': False, 'detail': 'Fichier absent : téléchargez-le de nouveau.'}
        actual = _sha256(path)
        if item['kind'] == 'tts_voice':
            from .piper_catalog import verify_md5
            try:
                verify_md5(path, item['md5'])
                verify_md5(path.with_name(path.name + '.json'), item['config_md5'])
            except (ValueError, OSError) as exc:
                return {'ok': False, 'sha256': actual, 'detail': str(exc)}
            return {'ok': True, 'sha256': actual, 'detail': 'Modèle et configuration conformes aux empreintes MD5 du catalogue officiel ; SHA-256 calculée localement.'}
        ok = actual == item['sha256']
        return {'ok': ok, 'sha256': actual, 'detail': 'Empreinte SHA-256 conforme à la source.' if ok else
                'Empreinte différente de celle publiée : supprimez puis téléchargez de nouveau.'}

    def remove(self, item_id):
        item = next((i for i in self.catalog_items() if i['id'] == item_id), None)
        if not item:
            raise ValueError('Élément vocal inconnu.')
        if item['kind'] in ('tts_engine', 'stt_engine'):
            engine = item['engine']
            if engine == 'phonon':
                if self.capture or self.transcribing: raise ValueError('Terminez la dictée avant de supprimer son moteur.')
                if self.phonon:
                    self.phonon.close()
                    self.phonon = None
            if engine == 'kyutai':
                if self.capture:
                    raise ValueError('Terminez la dictée avant de supprimer son moteur.')
                if self.stream:
                    self.stream.close()
                    self.stream = None
            for key in [k for k in self.tts_cache if k[0] == engine]:
                self.tts_cache.pop(key).close()
            self.python_envs.remove(engine)
            settings = self.settings()
            if engine in ('kyutai', 'phonon') and settings['stt']['engine'] == engine:
                settings['stt']['engine'] = 'whisper'
            if engine in ('pocket', *EXPRESSIVE_SPECS):
                if settings['tts']['voice'].startswith(engine+':'):
                    settings['tts']['voice'] = ''
                settings['connector_voices'] = {k: v for k, v in settings['connector_voices'].items() if not v.startswith(engine+':')}
            self.persist(settings)
            return {'ok': True}
        settings = self.settings()
        if item['kind'].endswith('runtime'):
            name = 'whisper-' + item['backend'] if item['kind'] == 'stt_runtime' else 'piper'
            record = settings['runtimes'].pop(name, None)
            if record and record.get('folder'):
                folder = Path(record['folder']).resolve()
                if folder.is_relative_to(self.runtimes_folder().resolve()) and folder.is_dir():
                    for engine in self.tts_cache.values():
                        engine.close()
                    self.tts_cache.clear()
                    shutil.rmtree(folder)
        else:
            record = settings['installed'].pop(item_id, None)
            if record:
                path = Path(record['path']).resolve()
                if path.is_relative_to(self.folder().resolve()):
                    for key in [k for k in self.tts_cache if k[0].startswith('piper:' + item_id)]:
                        self.tts_cache.pop(key).close()
                    if item['kind'] == 'tts_voice':
                        shutil.rmtree(path.parent, ignore_errors=True)
                    else:
                        path.unlink(missing_ok=True)
            if settings['stt']['model'] == item_id:
                settings['stt']['model'] = ''
            if settings['tts']['voice'].startswith('piper:' + item_id):
                settings['tts']['voice'] = ''
            settings['connector_voices'] = {k: v for k, v in settings['connector_voices'].items() if not v.startswith('piper:' + item_id)}
        self.persist(settings)
        return {'ok': True}

    def save_settings(self, data):
        settings = self.settings()
        stt, tts = dict(settings['stt']), dict(settings['tts'])
        given_stt, given_tts = data.get('stt') or {}, data.get('tts') or {}
        if 'model' in given_stt:
            if given_stt['model'] and given_stt['model'] not in settings['installed']:
                raise ValueError('Modèle Whisper non installé.')
            stt['model'] = given_stt['model']
        if 'language' in given_stt:
            if given_stt['language'] not in ('auto', 'fr', 'en'):
                raise ValueError('Langue de dictée invalide.')
            stt['language'] = given_stt['language']
        if 'engine' in given_stt:
            if given_stt['engine'] not in ('whisper', 'kyutai', 'phonon'):
                raise ValueError('Moteur de dictée invalide.')
            stt['engine'] = given_stt['engine']
        if 'phonon_model' in given_stt:
            if given_stt['phonon_model'] not in ('phonon-2', 'phonon-2.5'): raise ValueError('Modèle Phonon inconnu.')
            stt['phonon_model'] = given_stt['phonon_model']
        if 'device' in given_stt:
            if given_stt['device'] not in ('auto', 'cpu', 'gpu'):
                raise ValueError('Calcul invalide.')
            stt['device'] = given_stt['device']
        if 'threads' in given_stt:
            stt['threads'] = self._number(given_stt['threads'], 1, 32, 'Threads')

        def voice_key(value):
            value = str(value or '')
            if value and not re.fullmatch(r'(windows|piper|test|pocket|qwen|chatterbox|fish):.{1,120}', value):
                raise ValueError('Voix invalide.')
            backend, _, rest = value.partition(':')
            if backend in EXPRESSIVE_SPECS:
                valid = ['design'] + ['custom:'+n for n in SPEAKERS] if backend=='qwen' else ['default']
                valid += ['clone:'+s['id'] for s in settings['samples']]
                if rest not in valid: raise ValueError('Voix expressive inconnue.')
                if not self.python_envs.installed(backend): raise ValueError('Installez ce moteur vocal avant de le sélectionner.')
            if value.startswith('pocket:'):
                language, _, voice = value[7:].partition(':')
                if language not in POCKET_LANGUAGES or not (voice in POCKET_VOICES or
                                                            voice[6:] in {s['id'] for s in settings['samples']} and voice.startswith('clone:')):
                    raise ValueError('Voix Pocket TTS inconnue.')
            if value.startswith('piper:') and value.split(':')[1] not in settings['installed']:
                raise ValueError('Voix Piper non téléchargée.')
            return value
        if 'voice' in given_tts:
            tts['voice'] = voice_key(given_tts['voice'])
        if 'speed' in given_tts:
            tts['speed'] = self._number(given_tts['speed'], .5, 2.0, 'Vitesse', float)
        if 'volume' in given_tts:
            tts['volume'] = self._number(given_tts['volume'], 0, 100, 'Volume')
        for field in ('pocket_temperature', 'piper_noise_scale', 'piper_noise_w'):
            if field in given_tts:
                value = given_tts[field]
                tts[field] = None if value in (None, '') else self._number(value, 0, 2, field, float)
        for field, low, high in [('chatterbox_exaggeration',0,2),('chatterbox_cfg',0,1),('chatterbox_temperature',0.05,2),('fish_temperature',0.1,1),('fish_top_p',0.1,1)]:
            if field in given_tts: tts[field]=self._number(given_tts[field],low,high,field,float)
        if 'qwen_instruct' in given_tts: tts['qwen_instruct']=str(given_tts['qwen_instruct'] or '').strip()
        if 'fish_style' in given_tts:
            if given_tts['fish_style'] not in FISH_STYLES: raise ValueError('Style Fish inconnu.')
            tts['fish_style']=given_tts['fish_style']
        settings['stt'], settings['tts'] = stt, tts
        for field, low, high in (('silence_ms', 500, 4000), ('listen_timeout_s', 0, 86400), ('read_limit', 0, 20000), ('idle_unload_s', 30, 3600)):
            if field in data:
                settings[field] = self._number(data[field], low, high, field)
        for field in ('input_device', 'output_device'):
            if field in data:
                value = str(data[field] or '')
                names = self.audio.inputs() if field == 'input_device' else self.audio.outputs()
                if value and value not in names:
                    raise ValueError('Périphérique audio introuvable : ' + value)
                settings[field] = value
        if 'barge_in' in data:
            settings['barge_in'] = bool(data['barge_in'])
        if 'dictation_send' in data:
            settings['dictation_send'] = bool(data['dictation_send'])
        if 'connector_voices' in data:
            settings['connector_voices'] = {str(k): voice_key(v) for k, v in (data['connector_voices'] or {}).items()
                                            if k in self.service.engine.connectors and v}
        self.persist(settings)
        return {'ok': True}

    @staticmethod
    def _number(value, low, high, name, kind=int):
        try:
            number = kind(value)
        except (TypeError, ValueError):
            raise ValueError(name + ' : nombre attendu.')
        if not low <= number <= high:
            raise ValueError(f'{name} : entre {low} et {high}.')
        return number

    def samples_folder(self):
        return self.service.store.path.parent / 'voice-samples'

    def add_sample(self, name, consent, pcm=None, rate=None, source=None):
        '''A voice to copy, kept in the data folder. Only with the confirmation that you may use this voice.'''
        if consent is not True:
            raise ValueError('Confirmez que cette voix est la vôtre, ou que la personne a donné son accord.')
        from .voice_audio import read_wav, wav_bytes
        if source is not None:
            source = Path(source)
            if source.suffix.lower() != '.wav' or not source.is_file() or source.stat().st_size > 50 * 1024 * 1024:
                raise ValueError('Choisissez un fichier WAV de moins de 50 Mo.')
            try:
                pcm, rate, channels = read_wav(source.read_bytes())
            except Exception:
                raise ValueError('Ce fichier WAV n’est pas lisible (son 16 bits attendu).')
            if channels != 1:
                import array
                samples = array.array('h', pcm)
                pcm = array.array('h', (sum(samples[i:i + channels]) // channels for i in range(0, len(samples), channels))).tobytes()
        seconds = len(pcm) / 2 / rate
        if seconds < 3:
            raise ValueError('Échantillon trop court : au moins 3 secondes de parole.')
        identifier = uid()
        target = self.samples_folder() / (identifier + '.wav')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(wav_bytes(pcm[:int(rate * 30) * 2], rate))
        settings = self.settings()
        sample = {'id': identifier, 'name': safe_name(name) or 'Ma voix', 'file': str(target), 'seconds': round(min(seconds, 30), 1),
                  'created_at': now(), 'consent': True}
        settings['samples'].append(sample)
        self.persist(settings)
        return sample

    def record_sample(self, name, consent, seconds=12):
        '''Records a sample at your request: the microphone is open for these seconds only.'''
        if consent is not True:
            raise ValueError('Confirmez que cette voix est la vôtre, ou que la personne a donné son accord.')
        if self.capture:
            raise ValueError('Le micro est déjà ouvert.')
        from .voice_audio import level
        loud = []
        try:
            capture = self.audio.open_input(self.settings()['input_device'], lambda pcm: loud.append(level(pcm)), KyutaiSTT.RATE)
        except OSError as exc:
            raise ValueError(str(exc))
        time.sleep(self._number(seconds, 5, 30, 'Durée'))
        pcm = capture.stop()
        if sum(1 for value in loud if value > .35) * 50 < 2000:
            raise ValueError('Pas assez de parole entendue : parlez normalement pendant l’enregistrement.')
        return self.add_sample(name, consent, pcm, KyutaiSTT.RATE)

    def delete_sample(self, identifier):
        settings = self.settings()
        sample = next((s for s in settings['samples'] if s['id'] == identifier), None)
        if not sample:
            raise ValueError('Voix copiée introuvable.')
        path = Path(sample['file']).resolve()
        if path.is_relative_to(self.samples_folder().resolve()):
            path.unlink(missing_ok=True)
        settings['samples'] = [s for s in settings['samples'] if s['id'] != identifier]
        gone = 'clone:' + identifier
        if settings['tts']['voice'].endswith(gone):
            settings['tts']['voice'] = ''
        settings['connector_voices'] = {k: v for k, v in settings['connector_voices'].items() if not v.endswith(gone)}
        self.persist(settings)
        return {'ok': True}

    def set_hf_token(self, token):
        '''Read token for the Hugging Face models whose conditions you accepted (the voice copy of Pocket TTS).
        Kept encrypted by Windows with the other secrets, never in the configuration nor shown again.'''
        token = str(token or '').strip()
        if token and not re.fullmatch(r'hf_[A-Za-z0-9]{20,100}', token):
            raise ValueError('Jeton Hugging Face invalide (il commence par hf_).')
        self.service.engine.secrets.set('huggingface', token or None)
        for key in [k for k in self.tts_cache if k[0] == 'pocket']:
            self.tts_cache.pop(key).close()  # Reloaded with the voice copy weights at the next sentence.
        return {'configured': bool(token)}

    def hf_token_configured(self):
        secrets = self.service.engine.secrets
        try:
            return bool(secrets.get('huggingface')) if hasattr(secrets, 'get') else False
        except Exception:
            return False

    def microphone_test(self, seconds=2.5):
        """Opens the chosen microphone for a few seconds at your request, to see its level. Nothing is kept."""
        if self.capture:
            raise ValueError('Le micro est déjà ouvert.')
        from .voice_audio import level
        peaks = []
        try:
            capture = self.audio.open_input(self.settings()['input_device'], lambda pcm: peaks.append(level(pcm)))
        except OSError as exc:
            raise ValueError(str(exc))
        time.sleep(seconds)
        capture.stop()
        peak = max(peaks or [0])
        return {'peak': round(peak, 3), 'detail': 'Aucun son reçu : vérifiez le micro choisi et son niveau.' if peak < .25 else
                'Son faible : rapprochez-vous ou montez le gain.' if peak < .45 else 'Niveau correct.'}


def voice_action(service, action, data):
    if not action.startswith('voice_'):
        return UNHANDLED
    voice = service.voice
    if action == 'voice_state':
        return voice.state()
    if action == 'voice_settings':
        from .model_memory import hardware
        settings = voice.settings()
        try:
            inputs, outputs = voice.audio.inputs(), voice.audio.outputs()
        except OSError as exc:
            inputs, outputs, voice.error = [], [], str(exc)
        # Windows voice discovery may be slow. Show the settings before it finishes.
        if 'tts' not in voice.engines and (voice.windows_list is None or data.get('refresh')):
            with voice.lock:
                if not voice.windows_pending:
                    voice.windows_pending = True
                    voice.windows_list = voice.windows_list or []
                    def discover():
                        try: voice.windows_list = voice._windows().voices()
                        except Exception as exc: voice.error = 'Voix Windows indisponibles : ' + str(exc)
                        finally: voice.windows_pending = False
                    threading.Thread(target=discover, daemon=True).start()
        return {'windows_pending': voice.windows_pending, 'settings': {k: v for k, v in settings.items() if k not in ('runtimes', 'installed')},
                'hardware': hardware(), 'inputs': inputs, 'outputs': outputs, 'voices': voice.voices(),
                'connectors': sorted(service.engine.connectors), 'stt': voice.stt_status(settings),
                'samples': settings['samples'], 'hf_token': voice.hf_token_configured(),
                'engines': {k:voice.python_envs.installed(k) for k in ('pocket','kyutai','phonon',*EXPRESSIVE_SPECS)}}
    if action == 'voice_settings_save':
        return voice.save_settings(data)
    if action == 'voice_piper_refresh':
        from .piper_catalog import refresh
        def update(progress):
            voice.piper_items = refresh(voice.piper_cache)
        return service.local_models.job('Voix · Actualiser le catalogue Piper', update)
    if action == 'voice_catalog':
        return voice.catalog()
    if action == 'voice_install':
        return voice.install(data['id'])
    if action == 'voice_verify':
        return voice.verify(data['id'])
    if action == 'voice_remove':
        return voice.remove(data['id'])
    # Everything below is started by a click of the user in the page; none of it is offered to the agents.
    if action == 'voice_dictate':
        voice._bind(data['conversation_id'])
        voice.listen(data['conversation_id'], 'dictation')
        return voice.state()
    if action == 'voice_dictate_stop':
        threading.Thread(target=voice.finish_listening, args=(not data.get('cancel'),), daemon=True).start()
        return {'ok': True}
    if action == 'voice_conversation':
        voice.set_talking(data['conversation_id'], bool(data.get('on')))
        return voice.state()
    if action == 'voice_read':
        voice.set_reading(data['conversation_id'], bool(data.get('on')))
        return voice.state()
    if action == 'voice_transcript_done':
        with voice.wake:
            if voice.transcript and voice.transcript['id'] == data.get('id'):
                voice.measure('transcript_taken', transcript_id=data['id'])
                voice.transcript = None
                voice.last_activity = time.monotonic()
        return {'ok': True}
    if action == 'voice_resume_listening':
        voice.stop_speaking()
        voice._bind(data['conversation_id'])
        voice.listen(data['conversation_id'], 'conversation')
        return voice.state()
    if action == 'voice_stop':
        voice.stop_speaking()
        return {'ok': True}
    if action == 'voice_off':
        voice.off()
        return {'ok': True}
    if action == 'voice_read_message':
        message = service.store.one('SELECT * FROM messages WHERE id=?', (data['message_id'],))
        service.conversation(message['conversation_id'])
        text = planning_reply(message['content'])[0] if message['role'] == 'assistant' else message['content']
        return voice.speak(text, message['connector'])
    if action == 'voice_test':
        return voice.speak(data.get('text') or 'Bonjour, je suis la voix de CyAI. Voici comment je lirai les réponses.',
                           voice=data.get('voice') or voice.resolve_voice(data.get('connector')))
    if action == 'voice_microphone_test':
        return voice.microphone_test()
    if action == 'voice_sample_record':
        return voice.record_sample(data.get('name'), data.get('consent'), data.get('seconds', 12))
    if action == 'voice_sample_import':
        from .windows_ui import choose_file
        path = choose_file()
        if not path:
            return {'cancelled': True}
        return voice.add_sample(data.get('name'), data.get('consent'), source=path)
    if action == 'voice_sample_text':
        settings=voice.settings()
        sample=next((s for s in settings['samples'] if s['id']==data['id']),None)
        if not sample: raise ValueError('Échantillon absent.')
        sample['text']=str(data.get('text') or '').strip()
        voice.persist(settings)
        return {'ok':True}
    if action == 'voice_sample_delete':
        return voice.delete_sample(data['id'])
    if action == 'voice_hf_token':
        return voice.set_hf_token(data.get('token'))
    raise ValueError('Action vocale inconnue.')
