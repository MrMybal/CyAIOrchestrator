import hashlib
import json
import threading
import time
from types import SimpleNamespace
import unittest

import test_core
from cyai import app_mcp, voice as voice_module
from cyai.voice import Voice
from cyai.voice_text import Segmenter, planning_reply, speakable, usable_transcript

SPEECH = b'\x40\x1f\xc0\xe0' * 400      # 50 ms of a loud tone (16 kHz, 16 bits)
SILENCE = b'\x00\x00' * 800             # 50 ms of silence


class FakeCapture:
    def __init__(self, on_chunk, script):
        self.on_chunk, self.script, self.fed, self.running = on_chunk, list(script), [], True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        while self.running:
            chunk = self.script.pop(0) if self.script else SILENCE
            self.fed.append(chunk)
            self.on_chunk(chunk)
            time.sleep(.002)

    def stop(self):
        self.running = False
        self.thread.join(timeout=5)
        return b''.join(self.fed)


class FakeAudio:
    """A microphone that plays a script, and a speaker that writes down what it was asked to say."""

    def __init__(self):
        self.opened, self.played, self.script = 0, [], [SPEECH] * 10 + [SILENCE] * 40
        self.captures, self.rates = [], []

    def inputs(self):
        return ['Micro de test']

    def outputs(self):
        return ['Sortie de test']

    def open_input(self, device, on_chunk, rate=16000):
        self.opened += 1
        self.rates.append(rate)
        capture = FakeCapture(on_chunk, self.script)
        self.captures.append(capture)
        return capture

    def play(self, wav, device, volume, stop):
        self.played.append(wav.decode('utf-8'))
        return True


class FakeRecogniser:
    def __init__(self):
        self.text, self.calls = 'Lance les tests du projet', 0

    def transcribe(self, pcm, language):
        self.calls += 1
        return self.text


class FakeVoice:
    def synthesize(self, text):
        return text.encode('utf-8')


class Talker:
    """A connector that thinks, uses a tool and writes an answer in pieces, like Codex or Claude Code."""
    kind, speech_deltas = 'agent', True

    def __init__(self):
        self.config, self.hold = {}, threading.Event()
        self.hold.set()
        self.text = ("Bonjour ! J’ai terminé la correction demandée.\n```python\nprint('code à ne pas lire')\n```\n"
                     "| Fichier | État |\n|---|---|\nTout est prêt pour la relecture.\n<cyai-continuity>mémoire interne</cyai-continuity>")

    def check(self):
        return {'status': 'operational'}

    def run(self, prompt, root, model, native_id, control):
        control.emit('thinking', {'text': 'Je réfléchis à voix basse'})
        control.emit('tool', {'name': 'shell', 'command': 'pytest'})
        for i in range(0, len(self.text), 9):
            control.emit('delta', {'text': self.text[i:i + 9]})
            if i == 0:
                while not self.hold.is_set():
                    control.check()
                    time.sleep(.01)
        return self.text


def until(condition, seconds=10):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = condition()
        if value:
            return value
        time.sleep(.02)
    raise AssertionError('condition jamais remplie')


class VoiceTests(unittest.TestCase):
    """Voice in conversations: switched on only by the user, and it never decides which AI answers."""

    def setUp(self):
        self.fixture = test_core.CoreTests()
        self.fixture.setUp()
        self.s = self.fixture.service
        self.s.engine.connectors['talker'] = self.talker = Talker()
        self.audio, self.recogniser = FakeAudio(), FakeRecogniser()
        self.s.store.listeners.remove(self.s.voice.on_event)
        self.s.voice = self.s.engine.voice = Voice(self.s, self.audio, {'stt': self.recogniser, 'tts': lambda key: FakeVoice()})
        self.conversation = self.fixture.conversation

    def tearDown(self):
        self.fixture.tearDown()

    def send(self, text, connector='talker', **extra):
        mission = self.s.action('continue_conversation', {'conversation_id': self.conversation, 'connector': connector,
                                                          'instruction': text, **extra})['mission_id']
        return mission

    def spoken(self):
        return ' '.join(self.audio.played)

    def test_nothing_is_on_until_you_switch_it_on_and_no_agent_can(self):
        state = self.s.action('voice_state', {})
        self.assertEqual((state['phase'], state['microphone_open'], state['reading'], state['talking']), ('idle', False, False, False))
        mission = self.send('Bonjour')
        self.fixture.wait(mission)
        time.sleep(.3)
        self.assertEqual((self.audio.opened, self.audio.played), (0, []), 'ni micro ni lecture sans votre clic')
        self.assertFalse([name for name in app_mcp.ACTIONS if 'voice' in name or 'voix' in name], 'aucun outil MCP ne touche à la voix')
        self.s.action('voice_settings_save', {'tts': {'volume': 60}})
        restarted = Voice(self.s, FakeAudio(), {'stt': self.recogniser, 'tts': lambda key: FakeVoice()})
        self.assertEqual(restarted.state()['phase'], 'idle', 'les réglages enregistrés ne rallument rien au démarrage')
        self.assertFalse(restarted.reading or restarted.talking)
        self.s.store.listeners.remove(restarted.on_event)

    def test_a_dictation_comes_back_to_the_composer_and_is_not_sent(self):
        state = self.s.action('voice_dictate', {'conversation_id': self.conversation})
        self.assertTrue(state['microphone_open'])
        self.assertEqual(state['phase'], 'listening')
        time.sleep(.1)
        self.s.action('voice_dictate_stop', {})
        transcript = until(lambda: self.s.action('voice_state', {})['transcript'])
        self.assertEqual((transcript['text'], transcript['send'], transcript['conversation_id']), ('Lance les tests du projet', False, self.conversation))
        self.assertFalse(self.s.action('voice_state', {})['microphone_open'], 'le micro se ferme à la fin de la dictée')
        self.assertFalse(self.s.store.rows('SELECT id FROM missions WHERE conversation_id=?', (self.conversation,)), 'rien n’est envoyé sans vous')
        self.s.action('voice_transcript_done', {'id': transcript['id']})
        self.assertIsNone(self.s.action('voice_state', {})['transcript'])

    def test_silence_or_subtitles_noise_is_not_a_message(self):
        self.audio.script = [SILENCE] * 20
        self.s.action('voice_dictate', {'conversation_id': self.conversation})
        time.sleep(.1)
        self.s.voice.finish_listening()
        self.assertEqual(self.recogniser.calls, 0, 'un silence n’est pas transcrit')
        self.assertEqual(self.s.action('voice_state', {})['notice'], 'Rien entendu.')
        self.audio.script = [SPEECH] * 10
        self.recogniser.text = 'Sous-titres réalisés par la communauté d’Amara.org'
        self.s.action('voice_dictate', {'conversation_id': self.conversation})
        time.sleep(.1)
        self.s.voice.finish_listening()
        state = self.s.action('voice_state', {})
        self.assertIsNone(state['transcript'])
        self.assertEqual(state['notice'], 'Rien de compréhensible.')

    def test_a_dictated_message_is_an_ordinary_message_marked_voice(self):
        mission = self.send('Dicté', connector='alpha', input='voice')
        self.fixture.wait(mission)
        typed = self.send('Tapé', connector='alpha')
        self.fixture.wait(typed)
        rows = self.s.store.rows("SELECT content,input,connector FROM messages WHERE conversation_id=? AND role='user' ORDER BY seq", (self.conversation,))
        self.assertEqual([(r['content'], r['input']) for r in rows], [('Dicté', 'voice'), ('Tapé', '')])
        answer = self.s.store.rows("SELECT connector FROM messages WHERE conversation_id=? AND role='assistant'", (self.conversation,))
        self.assertEqual(answer[0]['connector'], 'alpha', 'l’IA est celle choisie dans la barre, pas par la voix')

    def test_only_the_words_of_the_answer_are_read(self):
        before = self.send('Avant')
        self.fixture.wait(before)
        self.s.action('voice_read', {'conversation_id': self.conversation, 'on': True})
        self.fixture.wait(self.send('Corrige le bug'))
        text = until(lambda: 'relecture' in self.spoken() and self.spoken())
        self.assertIn('Bonjour', text)
        self.assertIn('Tout est prêt pour la relecture.', text)
        for hidden in ('réfléchis', 'pytest', 'print', 'code à ne pas lire', 'Fichier', 'mémoire', 'cyai-continuity'):
            self.assertNotIn(hidden, text)
        self.assertEqual(text.count('Bonjour'), 1, 'la réponse d’avant l’activation n’est pas lue')

    def test_an_agent_without_clean_stream_is_read_when_its_answer_is_complete(self):
        self.s.action('voice_read', {'conversation_id': self.conversation, 'on': True})
        self.fixture.wait(self.send('Question', connector='beta'))
        self.assertEqual(until(lambda: self.audio.played), ['beta résultat vérifiable'])

    def test_stop_voice_is_not_cancel_the_answer(self):
        self.talker.hold.clear()
        self.s.action('voice_read', {'conversation_id': self.conversation, 'on': True})
        mission = self.send('Long travail')
        until(lambda: self.s.voice.segmenters)
        self.s.action('voice_stop', {})
        self.assertEqual(self.s.mission(mission)['status'], 'running', 'arrêter la voix laisse l’agent travailler')
        self.talker.hold.set()
        self.fixture.wait(mission)
        time.sleep(.4)
        self.assertNotIn('relecture', self.spoken(), 'la suite de cette réponse n’est plus lue')
        self.assertTrue(self.s.action('voice_state', {})['reading'], 'les réponses suivantes seront lues')

    def test_cancelling_the_answer_also_silences_it(self):
        self.talker.hold.clear()
        self.s.action('voice_read', {'conversation_id': self.conversation, 'on': True})
        mission = self.send('Long travail')
        until(lambda: self.s.voice.segmenters)
        self.s.action('cancel_mission', {'mission_id': mission})
        self.fixture.wait(mission)
        time.sleep(.3)
        self.assertEqual(self.s.mission(mission)['status'], 'cancelled')
        self.assertFalse(self.s.voice.streams)

    def test_a_voice_conversation_takes_turns(self):
        self.s.action('voice_settings_save', {'silence_ms': 500})
        self.s.action('voice_conversation', {'conversation_id': self.conversation, 'on': True})
        transcript = until(lambda: self.s.action('voice_state', {})['transcript'])
        self.assertTrue(transcript['send'], 'en conversation vocale, la fin de phrase envoie')
        self.assertFalse(self.s.voice.capture, 'le micro se ferme pendant la réponse')
        # The page sends it like a typed message, then says it did.
        mission = self.send(transcript['text'], input='voice')
        self.s.action('voice_transcript_done', {'id': transcript['id']})
        self.fixture.wait(mission)
        until(lambda: 'relecture' in self.spoken())
        until(lambda: self.audio.opened == 2)
        self.assertTrue(self.s.action('voice_state', {})['microphone_open'], 'le micro se rouvre après la réponse lue')
        self.s.action('voice_conversation', {'conversation_id': self.conversation, 'on': False})
        until(lambda: not self.s.voice.capture)

    def test_the_microphone_waits_while_the_conversation_is_busy(self):
        self.talker.hold.clear()
        mission = self.send('Travail en cours')
        until(lambda: self.s.mission(mission)['status'] == 'running')
        self.s.voice.set_reading(self.conversation, True)
        with self.s.voice.wake:
            self.s.voice.talking = True
        time.sleep(.5)
        self.assertEqual(self.audio.opened, 0, 'pas d’écoute pendant qu’un agent travaille')
        self.assertEqual(self.s.action('voice_state', {})['phase'], 'thinking')
        self.talker.hold.set()
        self.fixture.wait(mission)
        until(lambda: self.audio.opened == 1)

    def test_changing_conversation_turns_the_voice_off(self):
        other = self.s.action('create_conversation', {'project_id': self.fixture.project, 'title': 'Autre'})['id']
        self.s.action('voice_read', {'conversation_id': self.conversation, 'on': True})
        self.s.action('voice_dictate', {'conversation_id': other})
        state = self.s.action('voice_state', {})
        self.assertEqual((state['conversation_id'], state['reading']), (other, False))
        self.s.action('voice_off', {})
        self.assertFalse(self.s.action('voice_state', {})['microphone_open'])

    def test_a_message_is_read_on_request(self):
        self.fixture.wait(self.send('Question', connector='alpha'))
        message = self.s.store.rows("SELECT id FROM messages WHERE conversation_id=? AND role='assistant'", (self.conversation,))[0]
        self.s.action('voice_read_message', {'message_id': message['id']})
        self.assertEqual(until(lambda: self.audio.played), ['alpha résultat vérifiable'])

    def test_settings_are_checked_before_being_kept(self):
        for bad in ({'stt': {'language': 'klingon'}}, {'stt': {'device': 'tpu'}}, {'tts': {'speed': 5}},
                    {'input_device': 'Micro disparu'}, {'tts': {'voice': 'piper:fr_FR-siwis-medium'}}, {'silence_ms': 10}):
            with self.assertRaises(ValueError):
                self.s.action('voice_settings_save', bad)
        self.s.action('voice_settings_save', {'stt': {'language': 'en'}, 'input_device': 'Micro de test', 'tts': {'voice': 'windows:Hortense'},
                                              'connector_voices': {'alpha': 'windows:Zira', 'inconnu': 'windows:Zira'}})
        saved = json.loads(self.s.config_path.read_text(encoding='utf-8'))['voice']
        self.assertEqual((saved['stt']['language'], saved['input_device'], saved['connector_voices']), ('en', 'Micro de test', {'alpha': 'windows:Zira'}))
        self.assertEqual(self.s.voice.resolve_voice('alpha'), 'windows:Zira', 'la voix de l’agent d’abord')
        self.assertEqual(self.s.voice.resolve_voice('beta'), 'windows:Hortense', 'puis la voix générale')

    def test_the_catalogue_names_its_sources_and_adopts_an_intact_file(self):
        catalog = self.s.action('voice_catalog', {})
        for item in catalog['items']:
            self.assertTrue(item['source'].startswith('https://') and item['license'] and item['bytes'] > 0, item['id'])
            if item['kind'] == 'tts_voice':
                self.assertRegex(item['md5'], r'^[0-9a-f]{32}$')
                self.assertRegex(item['config_md5'], r'^[0-9a-f]{32}$')
            if item['kind'] == 'stt_model':
                self.assertRegex(item['sha256'], r'^[0-9a-f]{64}$')
            self.assertFalse(item['installed'])
        item = voice_module.ITEMS['whisper-tiny']
        original, content = item['sha256'], b'modele de test'
        item['sha256'] = hashlib.sha256(content).hexdigest()
        target = self.s.voice.folder() / 'whisper' / 'ggml-tiny.bin'
        target.parent.mkdir(parents=True)
        target.write_bytes(content)
        from cyai import local_models
        self.s.local_models = local_models.LocalModels.__new__(local_models.LocalModels)
        self.s.local_models.__dict__.update(service=self.s, config={}, jobs={}, pending=__import__('collections').deque(),
                                            worker_active=False, lock=threading.RLock(), loaded=None)
        real_download = local_models.download
        local_models.download = lambda *a, **k: (_ for _ in ()).throw(AssertionError('aucun téléchargement attendu'))
        try:
            self.s.action('voice_install', {'id': 'whisper-tiny'})
            job = until(lambda: next((j for j in self.s.local_models.jobs.values() if j['status'] in ('succeeded', 'failed')), None))
            self.assertEqual(job['status'], 'succeeded', job.get('error'))
            self.assertTrue(self.s.action('voice_verify', {'id': 'whisper-tiny'})['ok'])
            self.s.action('voice_remove', {'id': 'whisper-tiny'})
            self.assertFalse(target.exists())
        finally:
            item['sha256'] = original
            local_models.download = real_download

    def test_the_local_model_keeps_the_graphics_card(self):
        folder = self.fixture.root / 'moteurs'
        folder.mkdir()
        for name in ('cpu.exe', 'cuda.exe', 'modele.bin'):
            (folder / name).write_bytes(b'x')
        self.s.config['voice'] = {'runtimes': {'whisper-cpu': {'path': str(folder / 'cpu.exe')}, 'whisper-cuda': {'path': str(folder / 'cuda.exe')}},
                                  'installed': {'whisper-small': {'path': str(folder / 'modele.bin')}}}
        voice = Voice(self.s, FakeAudio())
        self.s.store.listeners.remove(voice.on_event)
        self.s.local_models = SimpleNamespace(loaded=None, config={'device': 'cpu', 'models': [{'id': 'm', 'settings': {'device': 'gpu'}}]})
        engine = voice._stt(voice.settings())
        self.assertEqual((engine.executable.name, engine.gpu), ('cuda.exe', True))
        self.s.local_models.loaded = 'm'
        engine = voice._stt(voice.settings())
        self.assertEqual((engine.executable.name, engine.gpu), ('cpu.exe', False), 'la VRAM reste au modèle local chargé')


class VoiceTextTests(unittest.TestCase):
    def test_the_first_sentence_leaves_early_and_code_is_never_read(self):
        segmenter = Segmenter()
        first = segmenter.feed('Voici le résultat de la vérification. Et la suite')
        self.assertEqual(first, ['Voici le résultat de la vérification.'])
        rest = segmenter.feed(' arrive.\n```\nsecret()\n```\n## Étapes\n1. Lire le fichier\n') + segmenter.flush()
        self.assertEqual(' '.join(rest), 'Et la suite arrive. Étapes. Lire le fichier.')

    def test_links_paths_tables_and_proposals_are_left_out(self):
        segments, truncated = speakable('Voir [la documentation](https://exemple.fr/doc) dans C:\\Projet\\notes.md.\n'
                                        '| a | b |\n### Sortie : rapport\nRapport prêt.\n### Proposition d’amélioration\nChanger la méthode.')
        self.assertEqual(' '.join(segments), 'Voir la documentation dans. Rapport prêt.')
        self.assertFalse(truncated)

    def test_a_long_answer_stops_at_the_limit(self):
        segments, truncated = speakable('Une phrase complète et assez longue pour compter. ' * 20, limit=200)
        self.assertTrue(truncated)
        self.assertLessEqual(sum(len(s) for s in segments), 200)

    def test_plans_and_noise(self):
        self.assertEqual(planning_reply('{"reply": "Voici le plan.", "plan": {"steps": []}}'), ('Voici le plan.', True))
        self.assertEqual(usable_transcript('[Musique]'), '')
        self.assertEqual(usable_transcript('  Ouvre le tableau  '), 'Ouvre le tableau')


if __name__ == '__main__':
    unittest.main()
