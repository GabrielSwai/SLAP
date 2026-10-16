# =====================================================================================
# Surrogate Language Alignment Program
#
# Check parsing and validation before spoken tokens enter the alignment algorithm.
# =====================================================================================

import unittest

from surrogate_aligner.aligner import align_sequences, make_surrogate_sequence
from surrogate_aligner.tones import make_word_sequence, parse_tones


# Class:        ToneParsingTests
# Description:  Checks accents, punctuation, and unparseable or mismatched transcription.

class ToneParsingTests(unittest.TestCase):
    def test_unicode_accents_and_default(self):
        self.assertEqual(parse_tones('á â à ā ǎ'), ['H', 'HL', 'L', 'M', 'LH'])
        self.assertEqual(parse_tones('a\u0301 a\u0302'), parse_tones('á â'))
        self.assertEqual(parse_tones('a', default_tone='M'), ['M'])

    # Standalone punctuation must not change how the two words consume the two notes
    def test_punctuation_does_not_consume_notes(self):
        phrase = 'á ! a'
        words = make_word_sequence(phrase.split(), parse_tones(phrase))
        self.assertEqual([word['word'] for word in words], ['á', 'a'])
        notes = make_surrogate_sequence([{'start': 0, 'end': .5}, {'start': .5, 'end': 1}], ['H', 'L'])
        alignment = align_sequences(words, notes)
        self.assertEqual([item['spoken']['word'] for item in alignment], ['á', 'a'])
        self.assertEqual(make_word_sequence(['---'], ['']), [])

    def test_unparseable_words_and_vowels(self):
        for phrase in ('ã', 'brrr', 'áã'):
            with self.subTest(phrase=phrase), self.assertRaises(ValueError):
                parse_tones(phrase)
        with self.assertRaises(ValueError):
            make_word_sequence(['a'], [''])
        with self.assertRaises(ValueError):
            make_word_sequence(['a', 'á'], ['L'])


if __name__ == '__main__':
    unittest.main()
