import threading
import unittest
from unittest.mock import patch
import test_voice
from test_voice import SPEECH, SILENCE, until

class VoiceFlowRegressionTests(unittest.TestCase):
    setUp = test_voice.VoiceTests.setUp
    tearDown = test_voice.VoiceTests.tearDown

    def manual(self):
        v=self.s.voice
        v._start_threads=lambda:None
        v.capture=type('Capture',(),{'retain':False})()
        v.capture_kind='conversation'
        v.floor=.2
        v._ending=False
        return v

    def test_sustained_speech_is_not_learned_as_noise_or_cut_at_two_minutes(self):
        v=self.manual()
        with patch('cyai.voice.threading.Thread') as thread:
            for _ in range(2500): v._chunk(SPEECH)
            self.assertEqual(v.silent_ms,0)
            self.assertEqual(v.heard_ms,125000)
            thread.assert_not_called()
        v.capture=None

    def test_pause_within_tolerance_does_not_send_but_real_silence_does(self):
        v=self.manual(); self.s.config['voice']={'silence_ms':1800}
        with patch('cyai.voice.threading.Thread') as thread:
            for _ in range(12):v._chunk(SPEECH)
            for _ in range(24):v._chunk(SILENCE)
            thread.assert_not_called()
            v._chunk(SPEECH)
            for _ in range(36):v._chunk(SILENCE)
            thread.assert_called_once()
        self.assertEqual(v.diagnostics[-1]['silence_ms'],1800)
        v.capture=None

    def test_barge_in_stops_once_and_keeps_utterance(self):
        v=self.manual();self.s.config['voice']={'barge_in':True}
        v.talking=True;v.synthesizing=True
        for _ in range(8):v._chunk(SPEECH)
        self.assertTrue(v.stop_event.is_set())
        self.assertEqual(v.generation,1)
        self.assertEqual(v.heard_ms,400)
        self.assertEqual(len([d for d in v.diagnostics if d['stage']=='interrupt_requested']),1)
        v.capture=None;v.synthesizing=False

    def test_no_barge_in_without_headphone_option(self):
        v=self.manual();v.talking=True;v.synthesizing=True
        for _ in range(8):v._chunk(SPEECH)
        self.assertFalse(v.stop_event.is_set())
        v.capture=None;v.synthesizing=False

    def test_synthesis_is_busy_before_audio_ready(self):
        v=self.s.voice;v.synthesizing=True
        self.assertTrue(v.speaking())
        v.synthesizing=False

    def test_continuous_timeout_zero_is_saved(self):
        self.s.voice.save_settings({'listen_timeout_s':0,'barge_in':True})
        self.assertEqual(self.s.voice.settings()['listen_timeout_s'],0)

    def test_stream_starts_before_generation_finishes_and_interrupt_drains(self):
        v=self.s.voice
        generated=threading.Event(); release=threading.Event(); played=threading.Event()
        def synth(text,key,on_audio=None,cancelled=None):
            on_audio(b'first');generated.set();release.wait(3)
            if not cancelled():on_audio(b'last')
        def play(chunks,done,device,volume,stop):
            self.assertEqual(chunks.get(timeout=2),b'first');played.set()
            stop.wait(2)
        v._synthesize=synth;self.audio.play_chunks=play
        try:
            v.speak('Une phrase assez longue pour vérifier le flux.',voice='pocket:french_24l:anna')
            self.assertTrue(played.wait(2))
            self.assertFalse(release.is_set())
            v.stop_speaking(); release.set()
            until(lambda:not v.synthesizing and not v.playing)
            self.assertFalse(v.ready)
        finally:release.set()

if __name__=='__main__':unittest.main()

class VoiceParameterTests(unittest.TestCase):
    setUp = test_voice.VoiceTests.setUp
    tearDown = test_voice.VoiceTests.tearDown

    def test_engine_settings_preserve_defaults_and_validate_without_partial_save(self):
        v = self.s.voice
        self.assertIsNone(v.settings()['tts']['pocket_temperature'])
        v.save_settings({'tts': {'pocket_temperature': .4, 'piper_noise_scale': .6, 'piper_noise_w': .8}})
        for bad in (float('nan'), float('inf'), -1, 3, 'bad'):
            with self.assertRaises(ValueError): v.save_settings({'tts': {'pocket_temperature': bad}})
            self.assertEqual(v.settings()['tts']['pocket_temperature'], .4)
        v.save_settings({'tts': {'pocket_temperature': None}})
        self.assertIsNone(v.settings()['tts']['pocket_temperature'])
        self.assertEqual(v.settings()['tts']['piper_noise_w'], .8)

    def test_clone_can_load_authorised_weights_after_offline_published_voice(self):
        from cyai.voice_python import PocketTTS
        from unittest.mock import MagicMock
        env = MagicMock()
        env.worker_env.return_value = {}
        worker = MagicMock(); worker.info = {'cloning': False}
        engine = PocketTTS(env, 'french_24l')
        with patch('cyai.voice_python._Worker', return_value=worker) as factory:
            engine._ensure_worker('anna')
            self.assertEqual(factory.call_args.args[1]['HF_HUB_OFFLINE'], '1')
            engine._ensure_worker('sample.wav')
            self.assertEqual(factory.call_count, 2)
            self.assertEqual(factory.call_args.args[1]['HF_HUB_OFFLINE'], '0')
            engine._ensure_worker('sample.wav')
            self.assertEqual(factory.call_count, 2, 'no repeated reload if access was denied')
        engine.close()
