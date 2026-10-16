# =====================================================================================
# Surrogate Language Alignment Program
#
# Verify native saving, startup diagnostics, and desktop server lifecycle.
# =====================================================================================

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from desktop import DesktopAPI, LocalServer, main, show_startup_error


# Class:        DesktopSaveTests
# Description:  Exercises saving without depending on a native window or webview backend.

class DesktopSaveTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.run = self.root / 'surrogate-aligner-example'
        self.run.mkdir()
        self.output = self.run / 'output.eaf'
        self.output.write_bytes(b'<ANNOTATION_DOCUMENT/>')
        self.api = DesktopAPI()
        self.api._window = MagicMock()
        self.tempdir_patch = patch('desktop.tempfile.gettempdir', return_value=str(self.root))
        self.tempdir_patch.start()
        self.addCleanup(self.tempdir_patch.stop)
        self.webview_patch = patch.dict('sys.modules', {
            'webview': SimpleNamespace(FileDialog=SimpleNamespace(SAVE=30))})
        self.webview_patch.start()
        self.addCleanup(self.webview_patch.stop)

    # A completed native save writes the actual EAF and then cleans up the upload
    def test_save_and_cleanup(self):
        destination = self.root / 'result'
        self.api._window.create_file_dialog.return_value = (str(destination),)
        self.assertEqual(self.api.save_output(self.run.name), {'saved': True})
        self.assertEqual(destination.with_suffix('.eaf').read_bytes(), b'<ANNOTATION_DOCUMENT/>')
        self.assertFalse(self.run.exists())
        self.assertEqual(list(self.root.glob('.slap-*')), [])

    # Cancelling the save dialog leaves the result available for retry
    def test_cancel_keeps_output(self):
        self.api._window.create_file_dialog.return_value = None
        self.assertEqual(self.api.save_output(self.run.name), {'cancelled': True})
        self.assertTrue(self.output.exists())

    # Appending .eaf must not bypass replacement consent for an existing file
    def test_extensionless_save_requires_overwrite_confirmation(self):
        destination = self.root / 'existing.eaf'
        destination.write_bytes(b'existing research data')
        self.api._window.create_file_dialog.return_value = (str(destination.with_suffix('')),)
        self.api._window.create_confirmation_dialog.return_value = False
        self.assertEqual(self.api.save_output(self.run.name), {'cancelled': True})
        self.assertEqual(destination.read_bytes(), b'existing research data')
        self.assertTrue(self.output.exists())
        self.api._window.create_confirmation_dialog.assert_called_once()
        self.api._window.create_confirmation_dialog.return_value = True
        self.assertEqual(self.api.save_output(self.run.name), {'saved': True})
        self.assertEqual(destination.read_bytes(), b'<ANNOTATION_DOCUMENT/>')

    # A failed write does not truncate an existing file or consume the generated result
    def test_failed_save_keeps_existing_destination(self):
        destination = self.root / 'existing.eaf'
        destination.write_bytes(b'existing')
        self.api._window.create_file_dialog.return_value = (str(destination),)
        with patch('desktop.os.replace', side_effect=PermissionError), self.assertLogs('slap.desktop'):
            self.assertIn('error', self.api.save_output(self.run.name))
        self.assertEqual(destination.read_bytes(), b'existing')
        self.assertTrue(self.output.exists())
        self.assertEqual(list(self.root.glob('.slap-*')), [])

    # Invalid run identifiers and unsafe output paths cannot be exported
    def test_rejects_invalid_sources_and_temporary_destination(self):
        for run_id in ('../outside', 'surrogate-aligner-../outside', None, 'surrogate-aligner-missing'):
            self.assertIn('error', self.api.save_output(run_id))
        self.api._window.create_file_dialog.assert_not_called()
        self.api._window.create_file_dialog.return_value = (str(self.run / 'saved.eaf'),)
        self.assertIn('error', self.api.save_output(self.run.name))
        self.assertTrue(self.output.exists())
        self.output.unlink()
        other = self.root / 'other.eaf'
        other.write_bytes(b'other')
        self.output.symlink_to(other)
        self.assertIn('error', self.api.save_output(self.run.name))


# Class:        DesktopLifecycleTests
# Description:  Verifies listener shutdown after normal operation and startup failures.

class DesktopLifecycleTests(unittest.TestCase):
    # Returning from the GUI loop closes the owned server after normal window closure
    def test_window_close_stops_server(self):
        webview = SimpleNamespace(settings={}, create_window=MagicMock(), start=MagicMock())
        with patch.dict('sys.modules', {'webview': webview}), \
                patch('desktop.configure_logging', return_value=Path('/tmp/slap-test.log')), \
                patch('desktop.LocalServer') as server:
            from frontend.app import app
            store = MagicMock()
            with patch.dict(app.config), patch.dict(app.extensions, {'runs': store}):
                self.assertEqual(main(), 0)
            store.close.assert_called_once()
            webview.start.assert_called_once_with(debug=False)
            self.assertTrue(webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER'])
            self.assertTrue(webview.create_window.call_args.kwargs['text_select'])
            server.return_value.__exit__.assert_called_once_with(None, None, None)

    # The local listener is closed whether its initial page succeeds or fails
    def test_server_lifecycle(self):
        for status in (200, 500):
            with self.subTest(status=status), patch('werkzeug.serving.make_server') as factory, \
                    patch('desktop.Thread') as thread, patch('desktop.HTTPConnection') as connection:
                factory.return_value.server_port = 12345
                connection.return_value.getresponse.return_value.status = status
                if status == 200:
                    with LocalServer(object()) as server:
                        self.assertEqual(server.url, 'http://127.0.0.1:12345')
                else:
                    with self.assertRaises(RuntimeError):
                        with LocalServer(object()):
                            self.fail('A failing home page must prevent startup')
                self.assertEqual(factory.call_args.args[:2], ('127.0.0.1', 0))
                factory.return_value.shutdown.assert_called_once()
                factory.return_value.server_close.assert_called_once()
                thread.return_value.join.assert_called_once()

    # Failures creating the desktop window still release the server and show diagnostics
    def test_window_failure_shows_error_and_closes_server(self):
        webview = SimpleNamespace(settings={}, create_window=MagicMock(side_effect=RuntimeError('GUI unavailable')))
        with patch.dict('sys.modules', {'webview': webview}), \
                patch('desktop.configure_logging', return_value=Path('/tmp/slap-test.log')), \
                patch('desktop.LocalServer') as server, patch('desktop.show_startup_error') as show_error, \
                self.assertLogs('slap.desktop'):
            from frontend.app import app
            store = MagicMock()
            with patch.dict(app.config), patch.dict(app.extensions, {'runs': store}):
                self.assertEqual(main(), 1)
            store.close.assert_called_once()
            server.return_value.__exit__.assert_called_once()
            self.assertIn('/tmp/slap-test.log', show_error.call_args.args[0])

    # The macOS fallback passes message text as data and never imports Tcl/Tk
    def test_macos_startup_alert_without_tkinter(self):
        message = 'A failure with "quotes" and a newline\nDiagnostic log: /tmp/slap.log'
        with patch('desktop.sys.platform', 'darwin'), patch('subprocess.run') as run, \
                patch.dict('sys.modules', {'tkinter': None}):
            show_startup_error(message)
        arguments = run.call_args.args[0]
        self.assertEqual(arguments[0], '/usr/bin/osascript')
        self.assertEqual(arguments[-1], message)
        self.assertNotIn(message, arguments[2])


if __name__ == '__main__':
    unittest.main()
