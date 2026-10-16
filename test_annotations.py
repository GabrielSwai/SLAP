# =====================================================================================
# Surrogate Language Aligner
#
# Verify temporary ambiguous surrogate tone export and its opt-out behavior.
# =====================================================================================

from copy import deepcopy
import unittest

import pympi

from surrogate_aligner.aligner import align_sequences, make_surrogate_sequence
from surrogate_aligner.annotations import add_alignment
from surrogate_aligner.tones import make_word_sequence


# Class:        AnnotationExportTests
# Description:  Checks that ambiguity changes only exported surrogate labels.

class AnnotationExportTests(unittest.TestCase):
    # Preserve words, spoken patterns, intervals, and input alignment in both export modes
    def test_ambiguous_export_and_opt_out(self):
        tiers = {'words': 'words', 'spoken_tones': 'spoken', 'surrogate_tones': 'notes'}
        words = make_word_sequence(['áa'], ['H-L'])
        notes = make_surrogate_sequence(
            [{'start': 0, 'end': 0.5}, {'start': 0.5, 'end': 1}], ['H', 'L'])
        alignment = align_sequences(words, notes)
        original = deepcopy(alignment)

        for ambiguous, expected in ((True, 'X-X'), (False, 'H-L')):
            with self.subTest(ambiguous=ambiguous):
                eaf = pympi.Elan.Eaf()
                add_alignment(eaf, alignment, tiers, ambiguous_surrogate_tones=ambiguous)
                self.assertEqual(eaf.get_annotation_data_for_tier('words'), [(0, 1000, 'áa')])
                self.assertEqual(eaf.get_annotation_data_for_tier('spoken'), [(0, 1000, 'H-L')])
                self.assertEqual(eaf.get_annotation_data_for_tier('notes'), [(0, 1000, expected)])
                self.assertEqual(alignment, original)

    # Keep insertion notes while leaving missing surrogate tones empty
    def test_insertions_and_missing_notes(self):
        tiers = {'words': 'words', 'spoken_tones': 'spoken', 'surrogate_tones': 'notes'}
        eaf = pympi.Elan.Eaf()
        alignment = align_sequences([], make_surrogate_sequence(
            [{'start': 0, 'end': 1}], ['L']))
        add_alignment(eaf, alignment, tiers)
        self.assertEqual(eaf.get_annotation_data_for_tier('notes'), [(0, 1000, 'X')])
        alignment = align_sequences(make_word_sequence(['a'], ['L']), [])
        add_alignment(eaf, alignment, tiers)
        self.assertEqual(eaf.get_annotation_data_for_tier('notes'), [])


if __name__ == '__main__':
    unittest.main()
