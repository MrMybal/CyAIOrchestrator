import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import test_voice
from cyai.voice_expressive import SPECS, CATALOG

class ExpressiveTests(unittest.TestCase):
    setUp=test_voice.VoiceTests.setUp
    tearDown=test_voice.VoiceTests.tearDown
    def installed(self):
        self.s.voice.engines.pop('tts',None)
        self.s.voice.python_envs.installed=lambda e:e in SPECS

    def test_catalog_and_selection_with_engine_specific_validation(self):
        self.installed(); v=self.s.voice
        keys={x['key'] for x in v.voices()}
        self.assertTrue({'qwen:design','qwen:custom:Ryan','chatterbox:default','fish:default'}<=keys)
        v.save_settings({'tts':{'voice':'qwen:custom:Ryan','qwen_instruct':'Soft and warm','fish_style':'whisper'}})
        with self.assertRaises(ValueError):v.save_settings({'tts':{'voice':'qwen:custom:unknown'}})
        with self.assertRaises(ValueError):v.save_settings({'tts':{'fish_temperature':2}})
        with self.assertRaises(ValueError):v.save_settings({'tts':{'chatterbox_cfg':float('nan')}})
        v.python_envs.installed=lambda _:False
        with self.assertRaises(ValueError):v.save_settings({'tts':{'voice':'fish:default'}})

    def test_switch_unloads_other_gpu_tts_and_passes_style_only_where_supported(self):
        self.installed();v=self.s.voice
        v.save_settings({'tts':{'qwen_instruct':'Warm adult voice','fish_style':'whisper'}})
        old=MagicMock();v.tts_cache[('chatterbox','default')]=old
        with patch('cyai.voice.ExpressiveTTS') as cls:
            v._synthesize('Bonjour','qwen:design')
            old.close.assert_called_once()
            options=cls.return_value.synthesize.call_args.args[1]
            self.assertEqual(options['instruct'],'Warm adult voice')
            self.assertEqual(options['language'],'fr')
            self.assertNotIn('temperature',options)

    def test_fish_clone_needs_transcription_and_reference_stays_a_local_path(self):
        self.installed();v=self.s.voice
        sample=v.add_sample('Référence',True,pcm=test_voice.SPEECH*80,rate=16000)
        key='fish:clone:'+sample['id']
        with self.assertRaisesRegex(ValueError,'transcription'):v._synthesize('Bonjour',key)
        self.s.action('voice_sample_text',{'id':sample['id'],'text':'Bonjour à tous.'})
        with patch('cyai.voice.ExpressiveTTS') as cls:
            v._synthesize('Bonjour',key)
            opts=cls.return_value.synthesize.call_args.args[1]
            self.assertEqual(opts['reference'],sample['file'])
            self.assertEqual(opts['reference_text'],'Bonjour à tous.')
        v.delete_sample(sample['id'])
        with self.assertRaisesRegex(ValueError,'absent'):v._synthesize('Bonjour',key)

    def test_design_requires_description_before_any_loading(self):
        self.installed()
        with patch('cyai.voice.ExpressiveTTS') as cls:
            with self.assertRaisesRegex(ValueError,'Décrivez'):self.s.voice._synthesize('Bonjour','qwen:design')
            cls.assert_not_called()
