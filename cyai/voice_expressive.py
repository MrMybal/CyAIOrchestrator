"""Local expressive TTS engines. Versions and capabilities are explicit; no cloud endpoint."""
from pathlib import Path
import base64
import threading
from .voice_audio import wav_bytes

FISH_COMMIT = '214da3cd841bda85da2496b96cd3c4d7edb1337e'
SPECS = {
 'qwen': {'packages': ['qwen-tts==0.1.1', 'truststore==0.10.4', 'torch==2.8.0', 'torchaudio==2.8.0'], 'torch':'cu128', 'worker':'expressive.worker', 'module':'qwen_tts', 'distribution':'qwen-tts', 'weights':[('Qwen--Qwen3-TTS-12Hz-1.7B-'+variant, 4200000000) for variant in ('VoiceDesign','CustomVoice','Base')]},
 'chatterbox': {'packages':['chatterbox-tts==0.1.7', 'truststore==0.10.4', 'setuptools==80.9.0'], 'torch':'cu124', 'worker':'expressive.worker', 'module':'chatterbox.mtl_tts', 'distribution':'chatterbox-tts', 'weights':[('ResembleAI--chatterbox', 3300000000)]},
 'fish': {'packages':['fish-speech @ https://github.com/fishaudio/fish-speech/archive/'+FISH_COMMIT+'.zip', 'truststore==0.10.4'], 'torch':'cu128', 'worker':'expressive.worker', 'module':'fish_speech.inference_engine', 'distribution':'fish-speech', 'weights':[('fishaudio--s2-pro', 11000000000)], 'overrides':['protobuf>=3.20,<6', 'tensorboard==2.18.0']},
}
CATALOG = [
 {'id':'qwen-tts','kind':'tts_engine','engine':'qwen','name':'Qwen3-TTS 1.7B · style et clonage','bytes':15500000000,'approx':True,'license':'Apache-2.0','source':'https://github.com/QwenLM/Qwen3-TTS','note':'Trois variantes : VoiceDesign, CustomVoice et Base. Français, consigne de style pour Design/Custom, clonage pour Base. CUDA ; génération par phrase dans cette intégration.'},
 {'id':'chatterbox-tts','kind':'tts_engine','engine':'chatterbox','name':'Chatterbox Multilingual · expression et clonage','bytes':6500000000,'approx':True,'license':'MIT','source':'https://github.com/resemble-ai/chatterbox','note':'Français, voix de référence, intensité expressive et guidage CFG. CUDA ; génération par phrase. Filigrane du moteur conservé.'},
 {'id':'fish-tts','kind':'tts_engine','engine':'fish','name':'Fish Audio S2 Pro · émotions','bytes':15000000000,'approx':True,'license':'Fish Audio Research License (poids : conditions spécifiques)','source':'https://github.com/fishaudio/fish-speech','note':'Balises expressives et clonage avec transcription de référence. CUDA, sans compilation Triton sous Windows. Le fournisseur recommande au moins 24 Go de VRAM : peut entrer en concurrence avec votre IA locale.'},
]
SPEAKERS = ('Vivian','Serena','Uncle_Fu','Dylan','Eric','Ryan','Aiden','Ono_Anna','Sohee')
DEFAULTS = {'qwen_instruct':'', 'chatterbox_exaggeration':0.5, 'chatterbox_cfg':0.5,
            'chatterbox_temperature':0.8, 'fish_style':'', 'fish_temperature':0.8, 'fish_top_p':0.8}
FISH_STYLES = ('', 'whisper', 'excited', 'angry', 'sad', 'happy')

class ExpressiveTTS:
    def __init__(self, environments, engine):
        self.environments, self.engine = environments, engine
        self.worker = None
        self.lock = threading.Lock()
        self.folder = environments.env_dir(engine) / 'work'
        self.folder.mkdir(parents=True, exist_ok=True)

    def synthesize_stream(self, text, options, on_audio, stop):
        from .voice_python import _Worker
        with self.lock:
            env = self.environments
            if not env.installed(self.engine):
                raise ValueError('Installez ce moteur dans Paramètres > Voix.')
            if not self.worker or not self.worker.alive():
                self.worker = _Worker([str(env.python(self.engine)), str(env.worker(self.engine)), 'serve', self.engine],
                                      {**env.worker_env(), 'HF_HUB_OFFLINE':'1'}, str(self.folder))
            self.worker.send({'text':text, **options})
            while True:
                answer = self.worker.next(900)
                if 'audio' in answer:
                    if not stop(): on_audio(wav_bytes(base64.b64decode(answer['audio']), answer['rate']))
                elif not answer.get('ok'):
                    raise RuntimeError(answer.get('error') or 'Le moteur vocal a échoué.')
                else: break

    def synthesize(self, text, options):
        from .voice_audio import read_wav
        parts=[]
        self.synthesize_stream(text, options, parts.append, lambda:False)
        if not parts: raise RuntimeError('Aucun audio produit.')
        decoded=[read_wav(p) for p in parts]
        return wav_bytes(b''.join(p[0] for p in decoded), decoded[0][1])

    def idle_for(self):
        return self.worker.idle_for() if self.worker else None

    def close(self):
        if self.worker: self.worker.close(); self.worker=None
