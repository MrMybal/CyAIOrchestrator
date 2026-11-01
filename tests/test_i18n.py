from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from cyai.i18n import bootstrap, language, messages, translate, translate_html
from cyai import workspace


class LocalizationTests(unittest.TestCase):
    def test_default_fallback_and_explicit_language(self):
        self.assertEqual(language(), 'en')
        self.assertEqual(language({'settings': {'language': 'fr'}}), 'fr')
        self.assertEqual(language({'settings': {'language': 'unknown'}}), 'en')

    def test_server_bootstrap_and_static_markup(self):
        for locale in ('en', 'fr'):
            script = bootstrap({'settings': {'language': locale}})
            self.assertIn('window.CYAI_LANGUAGE="' + locale + '"', script)
        original = '<button id="save" title="Enregistrer">Enregistrer</button><input value="Nom du projet">'
        self.assertEqual(translate_html(original), '<button id="save" title="Save">Save</button><input value="Nom du projet">')
        self.assertEqual(translate_html(original, 'fr'), original)

    def test_known_errors_and_unknown_provider_text(self):
        self.assertEqual(translate('Accès refusé.'), 'Access denied.')
        self.assertEqual(translate('Accès refusé.', 'fr'), 'Accès refusé.')
        self.assertEqual(translate('Exécutable absent : C:\\Example\\agent.exe. Configurez son chemin dans config.json.'), 'Executable missing: C:\\Example\\agent.exe. Configure its path in config.json.')
        self.assertEqual(translate('Voix · My Voice'), 'Voice · My Voice')
        self.assertEqual(translate('provider error with a user-owned path'), 'provider error with a user-owned path')

    def test_setting_persists_and_other_preferences_survive(self):
        service = SimpleNamespace(config={'settings': {'theme': 'dark', 'send_on_enter': False}})
        with patch.object(workspace, 'persist') as save:
            result = workspace.workspace_action(service, 'save_settings', {'language': 'fr'})
        self.assertTrue(result['ok']); save.assert_called_once_with(service)
        self.assertEqual(service.config['settings'], {'theme': 'dark', 'send_on_enter': False, 'language': 'fr'})
        with patch.object(workspace, 'persist'):
            workspace.workspace_action(service, 'save_settings', {'theme': 'ocean'})
        self.assertEqual(service.config['settings']['language'], 'fr')

    def test_invalid_language_does_not_mutate_settings(self):
        service = SimpleNamespace(config={'settings': {'theme': 'dark', 'language': 'fr'}})
        with self.assertRaises(ValueError):
            workspace.workspace_action(service, 'save_settings', {'language': '../en', 'theme': 'light'})
        self.assertEqual(service.config['settings'], {'theme': 'dark', 'language': 'fr'})

    def test_catalogue_shipped_in_package(self):
        self.assertGreater(len(messages()), 2000)
        self.assertIn('"locales/*.json"', (Path(__file__).resolve().parents[1] / 'pyproject.toml').read_text(encoding='utf-8'))
