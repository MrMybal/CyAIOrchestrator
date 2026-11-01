"""Phonon recognition on CPU, isolated from the desktop application."""
import tempfile
import threading
from pathlib import Path
from .voice_audio import wav_bytes
MODELS = ('phonon-2.5', 'phonon-2')
SPEC = {'packages': ['fermion-research==0.2.15'], 'torch': 'cpu', 'worker': 'phonon.worker', 'module': 'fermion', 'weights': [], 'cache_folder': 'phonon'}
class PhononSTT:
    def __init__(self, environments, model='phonon-2.5'):
        if model not in MODELS: raise ValueError('Modèle Phonon inconnu.')
        self.environments, self.model = environments, model
        self.worker = None
        self.lock = threading.Lock()
    def transcribe(self, pcm, language):
        if self.model == 'phonon-2' and language == 'fr':
            raise ValueError('Phonon-2 est anglais uniquement. Choisissez Phonon-2.5 pour le français.')
        from .voice_python import _Worker
        with self.lock, tempfile.TemporaryDirectory(prefix='cyai-phonon-') as folder:
            env = self.environments
            if not self.worker or not self.worker.alive():
                self.worker = _Worker([str(env.python('phonon')), str(env.worker('phonon')), 'serve', self.model], {**env.worker_env(), 'HF_HUB_OFFLINE': '1'}, str(env.env_dir('phonon')))
            source = Path(folder) / 'dictation.wav'
            source.write_bytes(wav_bytes(pcm))
            self.worker.send({'file': str(source)})
            answer = self.worker.next(300)
            if not answer.get('ok'): raise RuntimeError(answer.get('error') or 'Transcription Phonon impossible.')
            if answer.get('truncated'): raise RuntimeError('Phonon signale une transcription incomplète. Réessayez avec une phrase plus courte.')
            return answer.get('text', '')
    def idle_for(self):
        return self.worker.idle_for() if self.worker else 0
    def close(self):
        if self.worker:
            self.worker.close()
            self.worker = None
