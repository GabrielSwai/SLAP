# =====================================================================================
# Surrogate Language Aligner
#
# Verify frontend routes, alignment export, and temporary file cleanup.
# =====================================================================================

from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pympi
import soundfile as sf

from frontend.app import app
from surrogate_aligner.config import OUTPUT_TIERS
from surrogate_aligner.runs import RunStore


# Class:        FrontendTests
# Description:  Exercises uploads, processing, downloads, and invalid requests.

class FrontendTests(unittest.TestCase):
    # Create an isolated upload directory and a valid recording with ELAN annotations
    def setUp(self):
        self.store = RunStore()
        self.store_patch = patch.dict(app.extensions, {'runs': self.store})
        self.store_patch.start()
        self.addCleanup(self.store_patch.stop)
        self.addCleanup(self.store.close)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.tempdir_patch = patch('surrogate_aligner.runs.tempfile.gettempdir',
                                   return_value=self.directory.name)
        self.tempdir_patch.start()
        self.addCleanup(self.tempdir_patch.stop)
        self.client = app.test_client()
        sr = 16000
        times = np.arange(sr) / sr
        audio = BytesIO()
        sf.write(audio, 0.3 * np.sin(2 * np.pi * 180 * times), sr, format='WAV')
        self.audio = audio.getvalue()
        eaf = pympi.Elan.Eaf()
        eaf.add_tier('phrases')
        eaf.add_annotation('phrases', 0, 1000, 'a á')
        eaf_path = Path(self.directory.name) / 'source.eaf'
        eaf.to_file(str(eaf_path))
        self.annotations = eaf_path.read_bytes()

    # Upload fixtures through the public route rather than bypassing file validation
    def upload(self, annotations=None):
        response = self.client.post('/upload', data={
            'audio': (BytesIO(self.audio), 'recording.wav'),
            'elan': (BytesIO(self.annotations if annotations is None else annotations), 'source.eaf'),
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('phrases', response.json['tiers'])
        return response.json['run_id']

    # Verify the page and the complete processing flow using real acoustic features
    def test_alignment_download_and_cleanup(self):
        self.assertEqual(self.client.get('/').status_code, 200)
        run_id = self.upload()
        data = {'run_id': run_id, 'input_tier': 'phrases', 'default_tone': 'M'}
        response = self.client.post('/parse-tones', data=data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['segments'][0]['tones'], ['M', 'H'])

        # Fix onset locations to make this integration check independent of the detector
        with patch('frontend.app.detect_note_onsets', return_value=[0.0, 0.5]):
            response = self.client.post('/detect-notes', data=data)
        self.assertEqual(response.status_code, 200, response.json)
        self.assertTrue(response.json['output_ready'])
        self.assertEqual(response.json['processed_count'], 1)
        self.assertEqual(response.json['skipped_count'], 0)
        run_dir = Path(self.directory.name) / run_id
        output = pympi.Elan.Eaf(str(run_dir / 'output.eaf'))
        self.assertEqual(len(output.get_annotation_data_for_tier('phrases')), 1)
        tones = output.get_annotation_data_for_tier(OUTPUT_TIERS['spoken_tones'])
        self.assertEqual([label for _, _, label in sorted(tones)], ['M', 'H'])
        surrogate_tones = output.get_annotation_data_for_tier(OUTPUT_TIERS['surrogate_tones'])
        self.assertEqual([label for _, _, label in sorted(surrogate_tones)], ['X', 'X'])
        expected = (run_dir / 'output.eaf').read_bytes()
        response = self.client.get(f'/download/{run_id}')
        self.assertEqual(response.status_code, 200)
        self.assertIn('attachment', response.headers['Content-Disposition'])
        self.assertEqual(response.data, expected)
        response.close()
        self.assertFalse(run_dir.exists())
        self.assertEqual(self.client.get(f'/download/{run_id}').status_code, 404)

    # Reject invalid files, missing runs, and unsupported tone settings
    def test_invalid_requests(self):
        run_id = self.upload()
        self.assertEqual(self.client.post('/upload').status_code, 400)
        for route in ('/parse-tones', '/detect-notes'):
            self.assertEqual(self.client.post(route).status_code, 400)
            self.assertEqual(self.client.post(route, data={
                'run_id': '../outside', 'input_tier': 'phrases'}).status_code, 400)
            self.assertEqual(self.client.post(route, data={
                'run_id': 'surrogate-aligner-missing', 'input_tier': 'phrases'}).status_code, 404)
            self.assertEqual(self.client.post(route, data={
                'run_id': run_id, 'input_tier': 'phrases',
                'default_tone': 'H'}).status_code, 400)
        self.assertEqual(self.client.get('/download/invalid').status_code, 400)

    # Reject unknown tiers, silent detections, and annotations outside the audio
    def test_processing_errors(self):
        run_id = self.upload()
        data = {'run_id': run_id, 'input_tier': 'missing'}
        for route in ('/parse-tones', '/detect-notes'):
            self.assertEqual(self.client.post(route, data=data).status_code, 400)
        data['input_tier'] = 'phrases'
        with patch('frontend.app.detect_note_onsets', return_value=[]):
            response = self.client.post('/detect-notes', data=data)
        self.assertEqual(response.status_code, 400)
        self.assertFalse((Path(self.directory.name) / run_id / 'output.eaf').exists())
        with patch('frontend.app.get_elan_segments', return_value=[
                {'start': 0, 'end': 2, 'label': 'a'}]):
            self.assertEqual(self.client.post('/detect-notes', data=data).status_code, 400)

    # A phrase without onsets is explicitly reported rather than hidden in a successful export
    def test_partial_alignment_reports_skipped_interval(self):
        run_id = self.upload()
        segments = [{'start': 0, 'end': 0.5, 'label': 'á'},
                    {'start': 0.5, 'end': 1, 'label': 'a'}]
        with patch('frontend.app.get_elan_segments', return_value=segments), \
                patch('frontend.app.detect_note_onsets', side_effect=[[0], []]), \
                patch('frontend.app.extract_pitch', return_value=[180]), \
                patch('frontend.app.extract_shape', return_value=[0.5]):
            response = self.client.post('/detect-notes', data={'run_id': run_id, 'input_tier': 'phrases'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['total_count'], 2)
        self.assertEqual(response.json['processed_count'], 1)
        self.assertEqual(response.json['skipped_count'], 1)
        skipped = response.json['skipped_segments'][0]
        self.assertEqual((skipped['start'], skipped['end']), (0.5, 1))
        self.assertEqual(skipped['reason'], 'No note onsets detected.')

    # Both parse and detect reject unsupported transcription with an actionable phrase location
    def test_unparseable_words_are_rejected(self):
        run_id = self.upload()
        for route in ('/parse-tones', '/detect-notes'):
            with patch('frontend.app.get_elan_segments', return_value=[
                    {'start': 0, 'end': 1, 'label': 'ã'}]):
                response = self.client.post(route, data={'run_id': run_id, 'input_tier': 'phrases'})
            self.assertEqual(response.status_code, 400)
            self.assertIn('Phrase at 0.000s', response.json['error'])
            self.assertIn('Unsupported vowel', response.json['error'])

    # Replacing or explicitly abandoning an upload removes only the owning session's run
    def test_replacement_and_abandonment_cleanup(self):
        previous = self.upload()
        current = self.upload()
        self.assertFalse((Path(self.directory.name) / previous).exists())
        other_client = app.test_client()
        self.assertEqual(other_client.post(f'/runs/{current}/delete').status_code, 404)
        self.assertTrue((Path(self.directory.name) / current).exists())
        self.assertEqual(self.client.post(f'/runs/{current}/delete').status_code, 200)
        self.assertFalse((Path(self.directory.name) / current).exists())

    # Expired browser uploads report that researchers must upload their inputs again
    def test_expired_upload(self):
        run_id = self.upload()
        self.store.ttl_seconds = 0
        self.store.expire()
        response = self.client.post('/parse-tones', data={'run_id': run_id, 'input_tier': 'phrases'})
        self.assertEqual(response.status_code, 404)
        self.assertIn('expired', response.json['error'])


if __name__ == '__main__':
    unittest.main()
