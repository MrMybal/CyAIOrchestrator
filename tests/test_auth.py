import unittest
from unittest.mock import Mock, patch
from cyai.connectors import ClaudeCode


class AuthTests(unittest.TestCase):
    def test_status_uses_official_boolean_not_exit_code_alone(self):
        connector = ClaudeCode('claude-code', {}, None)
        with patch.object(connector, 'auth_cli', return_value='claude.exe'), patch('cyai.connectors.subprocess.run') as run:
            run.return_value = Mock(returncode=0, stdout='{"loggedIn":false}')
            self.assertEqual(connector.auth_status()['status'], 'disconnected')
            run.return_value = Mock(returncode=0, stdout='{"loggedIn":true}')
            self.assertEqual(connector.auth_status()['status'], 'connected')

    def test_login_reuses_pending_process(self):
        connector = ClaudeCode('claude-code', {}, None)
        with patch.object(connector, 'auth_cli', return_value='claude.exe'), patch.object(connector,'auth_status',return_value={'status':'disconnected'}), patch('cyai.connectors.subprocess.Popen') as popen:
            popen.return_value.poll.return_value = None
            connector.login()
            connector.login()
            self.assertEqual(popen.call_count, 1)
            self.assertEqual(popen.call_args.args[0], ['claude.exe', 'auth', 'login'])

    def test_connected_cli_does_not_open_login(self):
        connector=ClaudeCode('claude-code',{},None)
        with patch.object(connector,'auth_status',return_value={'status':'connected'}),patch('cyai.connectors.subprocess.Popen') as popen:
            self.assertEqual(connector.login()['status'],'connected')
            popen.assert_not_called()
