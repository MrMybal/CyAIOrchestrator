import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from cyai.desktop import DesktopService, service_available


class DesktopTests(unittest.TestCase):
    def test_existing_service_is_not_closed_by_window(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'config.json'
            config.write_text(json.dumps({'data_dir': '.data', 'allowed_roots': [directory]}))
            with patch('cyai.desktop.SecretStore'), patch('cyai.desktop.service_available', return_value=True), patch('cyai.desktop.InstanceLock') as lock:
                runtime = DesktopService(config)
                self.assertEqual(runtime.start(), 'http://127.0.0.1:8766')
                runtime.close()
                lock.assert_not_called()

    def test_bind_failure_releases_owned_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'config.json'
            config.write_text(json.dumps({'data_dir': '.data', 'allowed_roots': [directory]}))
            with patch('cyai.desktop.SecretStore'), patch('cyai.desktop.service_available', return_value=False), patch('cyai.desktop.InstanceLock') as lock, patch('cyai.desktop.Store') as store, patch('cyai.desktop.Engine') as engine, patch('cyai.desktop.registry'), patch('cyai.desktop.Service'), patch('cyai.desktop.make_server', side_effect=OSError('port occupé')):
                engine.return_value.worker.is_alive.return_value = False
                runtime = DesktopService(config)
                with self.assertRaises(OSError):
                    runtime.start()
                engine.return_value.shutdown.assert_called_once()
                store.return_value.close.assert_called_once()
                lock.return_value.close.assert_called_once()

    def test_no_token_never_reuses_unidentified_service(self):
        secret = Mock()
        secret.get.return_value = None
        with patch('cyai.desktop.urlopen') as connect:
            self.assertFalse(service_available('http://127.0.0.1:8766', secret))
            connect.assert_not_called()


class TrayTests(unittest.TestCase):
    def make_tray(self):
        from cyai.tray import WindowsTray
        tray = WindowsTray(Mock(), Mock())
        tray.icon = Mock()
        return tray

    def test_close_hides_without_stopping_service(self):
        tray = self.make_tray()
        args = Mock(CloseReason='UserClosing', Cancel=False)
        tray.on_closing(None, args)
        self.assertTrue(args.Cancel)
        tray.window.native.Hide.assert_called_once()
        tray.runtime.close.assert_not_called()

    def test_quit_and_windows_shutdown_are_not_cancelled(self):
        for quitting, reason in [(True, 'UserClosing'), (False, 'WindowsShutDown')]:
            tray = self.make_tray()
            tray.quitting = quitting
            args = Mock(CloseReason=reason, Cancel=False)
            tray.on_closing(None, args)
            self.assertFalse(args.Cancel)
            tray.window.native.Hide.assert_not_called()

    def test_dispose_removes_notification_icon(self):
        tray = self.make_tray()
        icon = tray.icon
        tray.dispose()
        self.assertFalse(icon.Visible)
        icon.Dispose.assert_called_once()
        tray.dispose()
