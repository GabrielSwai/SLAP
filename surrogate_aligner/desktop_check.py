# =====================================================================================
# Surrogate Language Alignment Program
#
# Exercise a frozen application using generated inputs and real audio analysis.
# =====================================================================================

from io import BytesIO
import json
import os
from pathlib import Path
import shutil
import tempfile
import traceback
from types import SimpleNamespace


# Function:     run_check
# Inputs:       report_path | destination for the diagnostic JSON report (str)
# Outputs:      status | process exit status (int)
# Description:  Checks bundled resources, analysis, native saving, and cleanup without a GUI.

def run_check(report_path):
    report = {'passed': False}
    run_dir = None
    try:
        from platformdirs import user_cache_path

        os.environ.setdefault('NUMBA_CACHE_DIR', str(
            user_cache_path('SLAP', appauthor=False, ensure_exists=True) / 'numba'))
        import numpy as np
        import pympi
        import soundfile as sf
        import webview
        from desktop import DesktopAPI, LocalServer
        from frontend.app import app
        from surrogate_aligner.config import OUTPUT_TIERS

        # Generate separate decaying notes to exercise the real onset and pitch detectors
        sr = 16000
        audio = np.zeros(sr * 3)
        times = np.arange(int(sr * .3)) / sr
        for index, onset in enumerate((.25, .85, 1.45, 2.05)):
            note = .7 * np.sin(2 * np.pi * (180 if index % 2 else 90) * times) * np.exp(-10 * times)
            start = round(onset * sr)
            audio[start:start + len(note)] += note
        stream = BytesIO()
        sf.write(stream, audio, sr, format='WAV')
        stream.seek(0)

        with tempfile.TemporaryDirectory(prefix='slap-check-') as directory:
            folder = Path(directory)
            eaf = pympi.Elan.Eaf()
            eaf.add_tier('phrases')
            eaf.add_annotation('phrases', 0, 3000, 'á a á a')
            source = folder / 'source.eaf'
            eaf.to_file(str(source))
            app.config['DESKTOP_MODE'] = True
            client = app.test_client()
            home = client.get('/')
            if home.status_code != 200 or b'data-desktop="true"' not in home.data:
                raise RuntimeError('Bundled home template did not render.')
            for resource in ('style.css', 'script.js'):
                if client.get(f'/static/{resource}').status_code != 200:
                    raise RuntimeError(f'Missing bundled asset: {resource}')
            response = client.post('/upload', data={
                'audio': (stream, 'recording.wav'),
                'elan': (BytesIO(source.read_bytes()), 'source.eaf'),
            })
            if response.status_code != 200:
                raise RuntimeError(f'Upload failed: {response.get_json()}')
            run_id = response.json['run_id']
            run_dir = Path(tempfile.gettempdir()) / run_id
            data = {'run_id': run_id, 'input_tier': 'phrases', 'default_tone': 'L'}
            for route in ('/parse-tones', '/detect-notes'):
                response = client.post(route, data=data)
                if response.status_code != 200:
                    raise RuntimeError(f'{route} failed: {response.get_json()}')
            report['detected_notes'] = len(response.json['segments'][0]['note_intervals'])
            api = DesktopAPI(app.extensions['runs'])
            destination = folder / 'aligned.eaf'

            # Substitute only the dialog selection; use the real native-save implementation
            api._window = SimpleNamespace(create_file_dialog=lambda *args, **kwargs: (str(destination),))
            saved = api.save_output(run_id)
            if not saved.get('saved'):
                raise RuntimeError(f'Native save failed: {saved}')
            output = pympi.Elan.Eaf(str(destination))
            annotations = output.get_annotation_data_for_tier(OUTPUT_TIERS['surrogate_tones'])
            if not annotations or any(set(label.split('-')) != {'X'} for _, _, label in annotations):
                raise RuntimeError('Expected ambiguous surrogate tones in exported annotations.')
            if run_dir.exists():
                raise RuntimeError('Run files were not cleaned up after saving.')

            # Verify the real loopback listener starts and stops in the frozen application
            with LocalServer(app) as server:
                report['local_server'] = server.url
            if server.thread.is_alive():
                raise RuntimeError('The local server did not stop.')
            report.update(passed=True, native_dialog='selection simulated',
                          exported_annotations=len(annotations), webview_imported=bool(webview))
    except Exception:
        report['error'] = traceback.format_exc()
    finally:
        if run_dir is not None:
            shutil.rmtree(run_dir, ignore_errors=True)
    Path(report_path).write_text(json.dumps(report, indent=2) + '\n')
    return 0 if report['passed'] else 1
