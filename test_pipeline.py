# =====================================================================================
# Surrogate Language Alignment Program
#
# Check that CLI diagnostics disclose partial output and preserve results on failure.
# =====================================================================================

from contextlib import ExitStack, redirect_stdout
from io import StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pympi

from surrogate_aligner.pipeline import run_pipeline


# Class:        PipelineTests
# Description:  Exercises skipped phrases and transcription errors in the command-line path.

class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.config = {'output_dir': root, 'audio_path': root / 'audio.wav',
                       'elan_input_path': root / 'input.eaf', 'input_tier': 'phrases',
                       'elan_output_path': root / 'output.eaf',
                       'output_tiers': {'words': 'words', 'spoken_tones': 'spoken', 'surrogate_tones': 'notes'}}
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch('surrogate_aligner.pipeline.load_audio', return_value=(np.zeros(16000), 16000, 1)))
        self.stack.enter_context(patch('surrogate_aligner.pipeline.load_elan', return_value=pympi.Elan.Eaf()))
        self.stack.enter_context(patch('surrogate_aligner.pipeline.extract_pitch', return_value=[180]))
        self.stack.enter_context(patch('surrogate_aligner.pipeline.extract_shape', return_value=[0.5]))

    # A partial CLI export identifies the exact skipped interval and still writes useful output
    def test_partial_export_reports_omissions(self):
        segments = [{'start': 0, 'end': .5, 'label': 'á'}, {'start': .5, 'end': 1, 'label': 'a'}]
        console = StringIO()
        with patch('surrogate_aligner.pipeline.get_elan_segments', return_value=segments), \
                patch('surrogate_aligner.pipeline.detect_note_onsets', side_effect=[[0], []]), \
                redirect_stdout(console):
            run_pipeline(self.config)
        self.assertIn('Aligned 1 of 2 phrases; 1 skipped.', console.getvalue())
        self.assertIn('Skipped 0.500–1.000s', console.getvalue())
        output = pympi.Elan.Eaf(str(self.config['elan_output_path']))
        self.assertEqual(output.get_annotation_data_for_tier('notes'), [(0, 500, 'X')])

    # An entirely empty or invalid analysis must not erase an existing intentional export
    def test_failed_analysis_preserves_existing_output(self):
        output = self.config['elan_output_path']
        output.write_bytes(b'existing research result')
        for label, onsets in (('á', []), ('ã', [0])):
            with self.subTest(label=label), \
                    patch('surrogate_aligner.pipeline.get_elan_segments', return_value=[
                        {'start': 0, 'end': 1, 'label': label}]), \
                    patch('surrogate_aligner.pipeline.detect_note_onsets', return_value=onsets), \
                    redirect_stdout(StringIO()), self.assertRaises(ValueError):
                run_pipeline(self.config)
            self.assertEqual(output.read_bytes(), b'existing research result')


if __name__ == '__main__':
    unittest.main()
