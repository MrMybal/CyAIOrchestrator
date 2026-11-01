import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
import unittest
import wave

import test_core
from test_voice import SILENCE, SPEECH, FakeAudio, FakeRecogniser, until
from cyai.voice import Voice
from cyai.voice_audio import wav_bytes
from cyai.voice_python import ENGINES, Environments

WORKERS = Path(__file__).resolve().parent.parent / 'cyai' / 'voice_workers'


class FakeSecrets:
    def __init__(self):
        self.values = {}

    def get(self, name):
        return self.values.get(name)

    def set(self, name, value):
        if value:
            self.values[name] = value
        else:
            self.values.pop(name, None)

    def redact(self, value):
        return value


class FakeStream:
    """Kyutai as the voice sees it: slow to load, words while you speak, the whole text at the end."""

    def __init__(self, delay=.2):
        time.sleep(delay)
        self.partial, self.fed, self.started = '', [], 0

    def begin(self):
        self.partial, self.fed = '', []
        self.started += 1

    def feed(self, pcm):
        self.fed.append(pcm)
        if len(self.fed) == 3:
            self.partial = ' Lance'

    def finish(self):
        return 'Lance les tests en direct'

    def alive(self):
        return True

    def idle_for(self):
        return 0

    def close(self):
        pass


class FakePocket:
    def __init__(self, language, calls):
        self.language, self.calls = language, calls

    def synthesize(self, text, voice):
        self.calls.append((self.language, voice, text))
        return text.encode('utf-8')

    def idle_for(self):
        return 0

    def close(self):
        pass


class VoiceEngineTests(unittest.TestCase):
    """Kyutai dictation in real time, Pocket TTS voices and copied voices, installed apart from CyAI."""

    def setUp(self):
        self.fixture = test_core.CoreTests()
        self.fixture.setUp()
        self.s = self.fixture.service
        self.s.engine.secrets = FakeSecrets()
        self.audio, self.recogniser, self.said = FakeAudio(), FakeRecogniser(), []
        self.streams = []

        def stream():
            self.streams.append(FakeStream())
            return self.streams[-1]
        self.s.store.listeners.remove(self.s.voice.on_event)
        self.s.voice = self.s.engine.voice = Voice(self.s, self.audio, {'stt': self.recogniser, 'stream': stream,
                                                                        'pocket': lambda language: FakePocket(language, self.said)})
        self.s.voice.windows_list = []  # No Windows voices in the tests: nothing is spoken for real.
        self.conversation = self.fixture.conversation

    def tearDown(self):
        self.fixture.tearDown()

    def test_kyutai_writes_the_words_while_you_speak(self):
        self.s.action('voice_settings_save', {'stt': {'engine': 'kyutai'}})
        self.audio.script = [SPEECH] * 30 + [SILENCE] * 200
        self.s.action('voice_dictate', {'conversation_id': self.conversation})
        self.assertEqual(self.audio.rates[-1], 24000, 'Kyutai écoute à 24 kHz')
        partial = until(lambda: self.s.action('voice_state', {})['partial'])
        self.assertEqual(partial, ' Lance')
        time.sleep(.1)
        self.s.action('voice_dictate_stop', {})
        transcript = until(lambda: self.s.action('voice_state', {})['transcript'])
        self.assertEqual(transcript['text'], 'Lance les tests en direct')
        self.assertEqual(self.recogniser.calls, 0, 'Whisper n’est pas appelé')
        capture = self.audio.captures[-1]
        self.assertEqual(len(self.streams[-1].fed), len(capture.fed), 'ce qui a été dit pendant le chargement n’est pas perdu')
        self.assertEqual(b''.join(self.streams[-1].fed), b''.join(capture.fed), 'et arrive dans l’ordre')
        self.assertEqual(self.s.action('voice_state', {})['partial'], '')

    def test_pocket_voices_come_first_and_a_copied_voice_needs_your_consent(self):
        voices = self.s.voice.voices()
        self.assertEqual(voices[0]['key'], 'pocket:french_24l:estelle')
        self.assertEqual(self.s.voice.resolve_voice('alpha'), 'pocket:french_24l:estelle', 'la voix française la plus naturelle par défaut')
        with self.assertRaises(ValueError):
            self.s.action('voice_sample_record', {'name': 'Moi', 'consent': False})
        self.audio.script = [SPEECH] * 80
        sample = self.s.voice.record_sample('Ma voix', True, 5)
        self.assertEqual(self.audio.rates[-1], 24000)
        self.assertTrue(Path(sample['file']).is_file())
        self.assertTrue(Path(sample['file']).resolve().is_relative_to(self.s.voice.samples_folder().resolve()))
        key = 'pocket:french_24l:clone:' + sample['id']
        self.assertIn(key, [v['key'] for v in self.s.voice.voices()])
        self.s.action('voice_settings_save', {'tts': {'voice': key}})
        self.s.voice.speak('Bonjour avec ma voix.')
        until(lambda: self.audio.played)
        self.assertEqual(self.said[-1][:2], ('french_24l', sample['file']), 'la voix copiée part de votre échantillon')
        self.s.action('voice_sample_delete', {'id': sample['id']})
        self.assertFalse(Path(sample['file']).exists())
        self.assertEqual(self.s.voice.settings()['tts']['voice'], '', 'la voix supprimée n’est plus utilisée')
        with self.assertRaises(ValueError):
            self.s.action('voice_settings_save', {'tts': {'voice': 'pocket:klingon:estelle'}})

    def test_an_imported_sample_is_checked(self):
        folder = Path(tempfile.mkdtemp(dir=self.fixture.root))
        stereo = folder / 'stereo.wav'
        output = io.BytesIO()
        with wave.open(output, 'wb') as file:
            file.setnchannels(2)
            file.setsampwidth(2)
            file.setframerate(16000)
            file.writeframes(b'\x10\x00\x20\x00' * 16000 * 4)
        stereo.write_bytes(output.getvalue())
        sample = self.s.voice.add_sample('Import', True, source=stereo)
        with wave.open(sample['file']) as file:
            self.assertEqual((file.getnchannels(), file.getframerate()), (1, 16000))
        (folder / 'court.wav').write_bytes(wav_bytes(b'\x00\x00' * 16000, 16000))
        (folder / 'voix.mp3').write_bytes(b'ID3')
        for bad in ('court.wav', 'voix.mp3'):
            with self.assertRaises(ValueError):
                self.s.voice.add_sample('Refus', True, source=folder / bad)

    def test_the_hugging_face_token_stays_secret(self):
        with self.assertRaises(ValueError):
            self.s.action('voice_hf_token', {'token': 'mauvais'})
        token = 'hf_' + 'a' * 34
        self.assertEqual(self.s.action('voice_hf_token', {'token': token}), {'configured': True})
        self.assertEqual(self.s.engine.secrets.get('huggingface'), token)
        settings = self.s.action('voice_settings', {})
        self.assertTrue(settings['hf_token'])
        self.assertNotIn(token, json.dumps(settings))
        self.assertNotIn(token, self.s.config_path.read_text(encoding='utf-8') if self.s.config_path.exists() else '')
        self.assertEqual(Environments(self.s.voice).worker_env()['HF_TOKEN'], token, 'donné au seul moteur de voix')
        self.assertEqual(Environments(self.s.voice).worker_env()['NO_TORCH_COMPILE'], '1', 'pas de Triton sous Windows')
        self.s.action('voice_hf_token', {'token': ''})
        self.assertIsNone(self.s.engine.secrets.get('huggingface'))

    def test_the_dictation_starts_offline(self):
        from unittest.mock import patch
        from cyai import voice_python
        seen = {}

        class Worker:
            def __init__(self, args, env, cwd, ready_timeout=900):
                seen.update(args=args, env=env)
                self.listeners = []
        with patch.object(voice_python, '_Worker', Worker):
            voice_python.KyutaiSTT(Environments(self.s.voice), 'auto')
        self.assertEqual(seen['env']['HF_HUB_OFFLINE'], '1', 'les poids sont déjà là : pas de réseau à chaque démarrage')
        self.assertEqual(seen['args'][-2:], ['serve', 'auto'])

    def test_the_real_secret_store_masks_the_token(self):
        from cyai.security import SecretStore
        store = SecretStore(Path(tempfile.mkdtemp(dir=self.fixture.root)))
        store.set('huggingface', 'hf_' + 'b' * 34)
        self.assertNotIn('hf_' + 'b' * 34, store.redact({'log': 'jeton hf_' + 'b' * 34}))

    def test_engines_install_apart_in_the_data_folder(self):
        envs = Environments(self.s.voice)
        commands = []

        def run(args, env, detail, progress, timeout=3600):
            commands.append((args, env))
            if args[1:2] == ['venv']:
                python = Path(args[-1]) / 'Scripts' / 'python.exe'
                python.parent.mkdir(parents=True)
                python.write_bytes(b'')
            return ['3.1.0 2.9.0 False']
        envs.run, envs.ensure_uv = run, lambda progress: 'uv.exe'
        envs.install('pocket', lambda *a: None)
        venv, install, prepare, check = commands
        runtimes = self.s.voice.runtimes_folder().resolve()
        self.assertEqual(venv[0][:4], ['uv.exe', 'venv', '--python', '3.12'])
        self.assertTrue(Path(venv[0][4]).resolve().is_relative_to(runtimes))
        self.assertEqual(venv[1]['UV_PYTHON_PREFERENCE'], 'only-managed', 'jamais le Python du système')
        self.assertTrue(Path(venv[1]['UV_PYTHON_INSTALL_DIR']).resolve().is_relative_to(runtimes))
        self.assertIn('--torch-backend', install[0])
        self.assertEqual(install[0][install[0].index('--torch-backend') + 1], 'cpu', 'Pocket TTS laisse la carte graphique libre')
        self.assertEqual(install[0][-1], 'pocket-tts==3.1.0')
        self.assertEqual(prepare[0][1:], [str(WORKERS / 'pocket.worker'), 'prepare'])
        self.assertTrue(Path(prepare[1]['HF_HOME']).resolve().is_relative_to(self.s.voice.folder().resolve()), 'les poids vont dans le dossier des modèles')
        self.assertTrue(envs.installed('pocket'))
        self.assertTrue(self.s.action('voice_catalog', {})['items'][[i['id'] for i in self.s.action('voice_catalog', {})['items']].index('pocket-tts')]['installed'])
        self.assertEqual(ENGINES['kyutai']['torch'], 'auto', 'Kyutai prend la version CUDA si le pilote NVIDIA est là')
        self.s.action('voice_remove', {'id': 'pocket-tts'})
        self.assertFalse(envs.env_dir('pocket').exists())


def fake_modules(folder):
    """Just enough of torch, pocket_tts and moshi to run the workers' protocol without the real libraries."""
    (folder / 'torch').mkdir()
    (folder / 'torch' / '__init__.py').write_text(textwrap.dedent('''
        import array, contextlib
        int16, float32, bfloat16 = 'int16', 'float32', 'bfloat16'
        class Tensor:
            def __init__(self, values): self.values = list(values)
            @property
            def shape(self): return (len(self.values),)
            def detach(self): return self
            def cpu(self): return self
            def float(self): return Tensor(float(v) for v in self.values)
            def clamp(self, low, high): return Tensor(min(high, max(low, v)) for v in self.values)
            def mul(self, k): return Tensor(v * k for v in self.values)
            def __truediv__(self, k): return Tensor(v / k for v in self.values)
            def to(self, what): return Tensor(int(v) for v in self.values) if what == int16 else self
            def numpy(self): return array.array('h', (int(v) for v in self.values))
            def __getitem__(self, key):
                if isinstance(key, tuple): return self
                return Tensor(self.values[key])
            def item(self): return self.values[0]
        def zeros(n): return Tensor([0.0] * n)
        def cat(items): return Tensor([v for t in items for v in t.values])
        def frombuffer(raw, dtype): return Tensor(array.array('h', bytes(raw)))
        def no_grad(): return contextlib.nullcontext()
        class cuda:
            @staticmethod
            def is_available(): return False
        class nn:
            class functional:
                @staticmethod
                def pad(t, pads): return Tensor(t.values + [0.0] * pads[1])
    '''), encoding='utf-8')
    (folder / 'pocket_tts').mkdir()
    (folder / 'pocket_tts' / '__init__.py').write_text(textwrap.dedent('''
        import torch
        class TTSModel:
            sample_rate, has_voice_cloning, temp = 24000, False, 0.7
            @classmethod
            def load_model(cls, language=None):
                print('bavardage de la bibliothèque')
                model = cls(); model.language = language; return model
            def get_state_for_audio_prompt(self, voice):
                if voice.endswith('.wav'): raise ValueError('voice cloning is not available')
                return voice
            def generate_audio(self, state, text):
                if text.startswith('temperature='): assert self.temp == float(text.split('=')[1])
                return torch.Tensor([0.5, -0.5, 2.0])
    '''), encoding='utf-8')
    (folder / 'moshi').mkdir()
    (folder / 'moshi' / '__init__.py').write_text('from . import models\n')
    (folder / 'moshi' / 'models.py').write_text(textwrap.dedent('''
        import contextlib, torch
        class Mimi:
            frame_size, frame_rate, sample_rate = 4, 10, 24000
            def __init__(self): self.frames = 0
            def streaming(self, n): return contextlib.nullcontext()
            def encode(self, chunk):
                if any(abs(v - 12345 / 32768) < 1e-6 for v in chunk.values): raise ValueError('trame illisible')
                self.frames += 1; return chunk
        class Tokens:
            def __init__(self, value): self.value = value
            def __getitem__(self, key): return torch.Tensor([self.value])
        class Tokenizer:
            def id_to_piece(self, token): return '\\u2581mot'
        class Info:
            stt_config = {'audio_silence_prefix_seconds': 0.2, 'audio_delay_seconds': 0.3}
            raw_config = {'text_padding_token_id': 3}
            def get_mimi(self, device): self.mimi = Mimi(); return self.mimi
            def get_text_tokenizer(self): return Tokenizer()
            def get_moshi(self, device, dtype): return 'lm'
        class loaders:
            class CheckpointInfo:
                @staticmethod
                def from_hf_repo(repo): return Info()
        class LMGen:
            def __init__(self, lm, temp, temp_text): self.steps = 0
            def streaming(self, n):
                self.steps = 0  # Like the real one: a new utterance starts from a fresh state.
                return contextlib.nullcontext()
            def step(self, codes):
                self.steps += 1
                return Tokens(7 if self.steps % 5 == 0 else 3)
    '''), encoding='utf-8')


class WorkerProtocolTests(unittest.TestCase):
    """The workers speak one JSON line per answer on stdout; whatever the libraries print goes elsewhere."""

    def run_worker(self, name, args, requests):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            fake_modules(folder)
            env = {**os.environ, 'PYTHONPATH': str(folder), 'PYTHONIOENCODING': 'utf-8'}
            requests = [r(folder) if callable(r) else r for r in requests]
            result = subprocess.run([sys.executable, str(WORKERS / name), *args], input=''.join(json.dumps(r) + '\n' for r in requests),
                                    capture_output=True, text=True, encoding='utf-8', env=env, timeout=60)
            lines = [json.loads(line) for line in result.stdout.splitlines()]
            files = {p.name: p.read_bytes() for p in folder.glob('*.wav')}
            return lines, result.stderr, files

    def test_pocket_worker(self):
        lines, stderr, files = self.run_worker('pocket.worker', ['serve', 'french_24l'], [
            lambda f: {'text': 'Bonjour', 'voice': 'estelle', 'file': str(f / 'phrase.wav')},
            lambda f: {'text': 'Copie', 'voice': str(f / 'moi.wav'), 'file': str(f / 'copie.wav')}])
        self.assertEqual(lines[0], {'ok': True, 'ready': True, 'cloning': False, 'sample_rate': 24000})
        self.assertEqual(lines[1], {'ok': True})
        self.assertIn('bavardage', stderr, 'les messages de la bibliothèque ne passent pas par le protocole')
        with wave.open(io.BytesIO(files['phrase.wav'])) as file:
            self.assertEqual((file.getframerate(), file.getsampwidth(), file.readframes(3)), (24000, 2, b'\xff\x3f\x01\xc0\xff\x7f'))
        self.assertFalse(lines[2]['ok'])
        self.assertIn('Hugging Face', lines[2]['error'], 'la copie de voix explique comment obtenir l’accès')

    def test_pocket_temperature_resets_to_model_default_and_rejects_invalid(self):
        lines, _, _ = self.run_worker('pocket.worker', ['serve', 'french_24l'], [
            lambda f: {'text': 'temperature=0.25', 'voice': 'anna', 'temperature': .25, 'file': str(f / 'a.wav')},
            lambda f: {'text': 'temperature=0.7', 'voice': 'anna', 'temperature': None, 'file': str(f / 'b.wav')},
            lambda f: {'text': 'invalid', 'voice': 'anna', 'temperature': 'NaN', 'file': str(f / 'c.wav')}])
        self.assertTrue(lines[1]['ok']); self.assertTrue(lines[2]['ok'])
        self.assertFalse(lines[3]['ok'])

    def test_kyutai_worker(self):
        import base64
        audio = base64.b64encode(b'\x00\x10' * 10).decode()
        lines, stderr, _ = self.run_worker('kyutai.worker', ['serve', 'auto'], [
            {'op': 'start'}, {'op': 'audio', 'pcm': audio}, {'op': 'end'}, {'op': 'end'}])
        self.assertEqual(lines[0], {'ok': True, 'ready': True, 'device': 'cpu', 'sample_rate': 24000})
        pieces = [line['piece'] for line in lines if 'piece' in line]
        finals = [line for line in lines if 'final' in line]
        # 2 prefix frames + 3 audio frames (10 samples, the last padded) + 3 delay frames = 8 steps: 1 word.
        self.assertEqual(pieces, [' mot'])
        self.assertEqual(finals, [{'ok': True, 'final': 'mot'}, {'ok': True, 'final': ''}])

    def test_an_error_while_listening_is_answered_once_at_the_end(self):
        import base64
        bad, good = base64.b64encode(bytes([0x39, 0x30]) * 4).decode(), base64.b64encode(bytes([0x00, 0x10]) * 10).decode()
        lines, _, _ = self.run_worker('kyutai.worker', ['serve', 'auto'], [
            {'op': 'start'}, {'op': 'audio', 'pcm': bad}, {'op': 'audio', 'pcm': good}, {'op': 'end'},
            {'op': 'start'}, {'op': 'audio', 'pcm': good}, {'op': 'end'}])
        answers = [line for line in lines[1:] if 'piece' not in line]
        self.assertEqual(len(answers), 2, 'une réponse par phrase, pas une de plus')
        self.assertEqual((answers[0]['ok'], answers[0]['error']), (False, 'trame illisible'))
        self.assertEqual(answers[1], {'ok': True, 'final': 'mot'}, 'la dictée suivante reçoit sa propre réponse')


if __name__ == '__main__':
    unittest.main()
