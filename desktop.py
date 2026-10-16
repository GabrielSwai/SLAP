# =====================================================================================
# Surrogate Language Alignment Program
#
# Launch the local Flask interface in a native desktop window.
# =====================================================================================

from http.client import HTTPConnection
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import shutil
import sys
import tempfile
from threading import Thread


# Class:        LocalServer
# Description:  Owns a loopback-only server and stops it when the desktop window exits.

class LocalServer:
    def __init__(self, app):
        from werkzeug.serving import make_server

        # Let the operating system select an available local port
        self.server = make_server('127.0.0.1', 0, app, threaded=True)
        self.thread = Thread(target=self.server.serve_forever, name='slap-server', daemon=True)
        self.url = f'http://127.0.0.1:{self.server.server_port}'

    def __enter__(self):
        self.thread.start()
        try:
            # Verify that the initial page renders before opening the window
            connection = HTTPConnection('127.0.0.1', self.server.server_port, timeout=10)
            try:
                connection.request('GET', '/')
                response = connection.getresponse()
                response.read()
                if response.status != 200:
                    raise RuntimeError('The SLAP home page could not be loaded.')
            finally:
                connection.close()
        except Exception:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        # Closing the GUI loop also releases the listener and its server thread
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


# Class:        DesktopAPI
# Description:  Saves completed ELAN results through the native save dialog.

class DesktopAPI:
    def __init__(self, run_store=None):
        self._window = None
        self._run_store = run_store

    # Function:     save_output
    # Inputs:       run_id | identifier returned by the upload route (str)
    # Outputs:      result | saved, cancelled, or error status (dict)
    # Description:  Keeps results on cancellation or failure and removes them after saving.

    def save_output(self, run_id):
        import webview

        # Only permit output from a valid upload directory
        if (not isinstance(run_id, str) or not run_id.startswith('surrogate-aligner-')
                or Path(run_id).name != run_id or '/' in run_id or '\\' in run_id):
            return {'error': 'Invalid run ID.'}
        run_dir = Path(tempfile.gettempdir()) / run_id
        output = run_dir / 'output.eaf'
        if run_dir.is_symlink() or output.is_symlink() or not output.is_file():
            return {'error': 'The aligned ELAN file was not found. Process the recording again.'}

        temporary_path = None
        lease = None
        try:
            if self._run_store is not None:
                lease = self._run_store.acquire(run_id)
            selection = self._window.create_file_dialog(
                webview.FileDialog.SAVE,
                save_filename='aligned_output.eaf',
                file_types=('ELAN annotations (*.eaf)',),
            )
            if not selection:
                return {'cancelled': True}
            destination = Path(selection if isinstance(selection, str) else selection[0])
            extension_added = destination.suffix.lower() != '.eaf'
            if extension_added:
                destination = destination.with_name(destination.name + '.eaf')
            if destination.resolve().is_relative_to(run_dir.resolve()):
                return {'error': 'Choose a save location outside the temporary analysis folder.'}

            # The native dialog confirms its selected path; confirm any renamed destination too
            if extension_added and destination.exists() and not self._window.create_confirmation_dialog(
                    'Replace ELAN file?', f'{destination.name} already exists. Replace it?'):
                return {'cancelled': True}

            # Replace the destination only after a complete copy has been written
            with tempfile.NamedTemporaryFile(dir=destination.parent, prefix='.slap-',
                                             suffix='.eaf', delete=False) as target:
                temporary_path = Path(target.name)
                with output.open('rb') as source:
                    shutil.copyfileobj(source, target)
            os.replace(temporary_path, destination)
            temporary_path = None
            if self._run_store is not None:
                self._run_store.discard(run_id)
            else:
                shutil.rmtree(run_dir, ignore_errors=True)
            return {'saved': True}
        except Exception:
            logging.getLogger('slap.desktop').exception('Could not save the ELAN output')
            return {'error': 'Could not save the ELAN file. Check the folder permissions and try again.'}
        finally:
            if lease is not None:
                lease.close()
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)


# Function:     configure_logging
# Inputs:       None
# Outputs:      log_path | location of the rotating diagnostic log (Path)
# Description:  Records startup and analysis failures outside the application installation.

def configure_logging():
    from platformdirs import user_log_path

    log_path = user_log_path('SLAP', appauthor=False, ensure_exists=True) / 'desktop.log'
    handler = RotatingFileHandler(log_path, maxBytes=2_000_000, backupCount=2, encoding='utf-8')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
    logging.getLogger().addHandler(handler)
    logging.getLogger().setLevel(logging.INFO)
    return log_path


# Function:     show_startup_error
# Inputs:       message | recovery instructions and diagnostic log location (str)
# Outputs:      None
# Description:  Presents startup failures even when the webview cannot initialize.

def show_startup_error(message):
    # Use the system alert on macOS, which does not require a bundled Tcl/Tk runtime
    if sys.platform == 'darwin':
        import subprocess

        try:
            subprocess.run([
                '/usr/bin/osascript', '-e',
                'on run argv\ndisplay alert "SLAP could not start" message (item 1 of argv) as critical\nend run',
                message,
            ], check=True)
            return
        except Exception:
            logging.getLogger('slap.desktop').exception('Could not display the macOS startup alert')
    root = None
    try:
        import tkinter
        from tkinter import messagebox

        root = tkinter.Tk()
        root.withdraw()
        messagebox.showerror('SLAP could not start', message, parent=root)
    except Exception:
        # Retain readable diagnostics when no graphical error dialog is available
        if sys.stderr is not None:
            print(message, file=sys.stderr)
    finally:
        if root is not None:
            root.destroy()


# Function:     main
# Inputs:       None
# Outputs:      status | process exit status (int)
# Description:  Opens SLAP and releases the server when the desktop window closes.

def main():
    log_path = None
    run_store = None
    try:
        log_path = configure_logging()
        # Keep JIT caches outside the signed, read-only application bundle
        if getattr(sys, 'frozen', False):
            from platformdirs import user_cache_path

            os.environ.setdefault('NUMBA_CACHE_DIR', str(
                user_cache_path('SLAP', appauthor=False, ensure_exists=True) / 'numba'))
        import webview
        from frontend.app import app

        app.config['DESKTOP_MODE'] = True
        app.config['TEMPLATES_AUTO_RELOAD'] = False
        run_store = app.extensions['runs']
        api = DesktopAPI(run_store)
        webview.settings['OPEN_EXTERNAL_LINKS_IN_BROWSER'] = True
        with LocalServer(app) as server:
            api._window = webview.create_window(
                'SLAP', server.url, js_api=api, width=1200, height=820,
                min_size=(640, 540), text_select=True,
            )
            logging.getLogger('slap.desktop').info('Starting desktop window')
            webview.start(debug=False)
        return 0
    except Exception:
        logging.getLogger('slap.desktop').exception('Desktop startup failed')
        if getattr(sys, 'frozen', False):
            message = ('SLAP could not start. Please reinstall the application. '
                       'If the problem continues, share the diagnostic log with the developer.')
        else:
            message = ('SLAP could not start. If running from source, install the desktop dependencies:\n'
                       'python -m pip install -r requirements-desktop.txt\n\n'
                       'If the problem continues, share the diagnostic log with the developer.')
        if log_path is not None:
            message += f'\n\nDiagnostic log: {log_path}'
        show_startup_error(message)
        return 1
    finally:
        if run_store is not None:
            run_store.close()


if __name__ == '__main__':
    # Exercise packaged resources and analysis without requiring a graphical session
    if len(sys.argv) == 3 and sys.argv[1] == '--smoke-test':
        from surrogate_aligner.desktop_check import run_check

        sys.exit(run_check(sys.argv[2]))
    sys.exit(main())
