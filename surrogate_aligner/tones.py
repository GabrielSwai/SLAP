# =====================================================================================
# Surrogate Language Aligner
#
# Parse Kinande phrases and construct word-level tone sequences.
# =====================================================================================


import unicodedata


# Function:     parse_tones
# Inputs:       tone_string | spoken phrase (str)
#               default_tone | tone for unmarked vowels ("L" or "M")
# Outputs:      tones | parsed word-level tone patterns (list)
# Description:  Converts a phrase like "Tukándisyá tasáta kwȇ?" into a list of tone patterns like ["L-H-L-H", "L-H-L", "HL"].

def parse_tones(tone_string, default_tone="L"):
    if default_tone not in ("L", "M"):
        raise ValueError('default_tone must be "L" or "M".')

    # Unmarked vowels take the selected default tone
    # Include Latin and IPA vowel letters and their available uppercase forms.
    # Leave language-dependent vowel letters such as y and w out of this list.
    default_vowels = [
        "a", "e", "i", "o", "u", "A", "E", "I", "O", "U",
        "ɛ", "Ɛ", "ɔ", "Ɔ", "ə", "Ə", "ɨ", "Ɨ", "ʉ", "Ʉ", "ɪ", "Ɩ", "ʊ", "Ʊ",
        "æ", "Æ", "ø", "Ø", "œ", "Œ", "ɐ", "Ɐ", "ɑ", "Ɑ", "ɒ", "Ɒ",
        "ɘ", "Ǝ", "ɵ", "Ɵ", "ɜ", "Ɜ", "ɞ", "ɤ", "Ɤ", "ɯ", "Ɯ", "ɶ",
        "ʌ", "Ʌ", "ʏ", "ɚ", "ɝ",
    ]

    # Use decomposed spellings so each tone mark stays with its vowel
    h_vowels = [vowel + "\u0301" for vowel in default_vowels]   # Acute: H
    m_vowels = [vowel + "\u0304" for vowel in default_vowels]   # Macron: M
    l_vowels = [vowel + "\u0300" for vowel in default_vowels]   # Grave: L
    sh_vowels = [vowel + "\u030b" for vowel in default_vowels]  # Double acute: SH
    sl_vowels = [vowel + "\u030f" for vowel in default_vowels]  # Double grave: SL

    # Add unmarked vowels to the selected tone's list
    if default_tone == "L":
        l_vowels += default_vowels
    else:
        m_vowels += default_vowels

    # Vowels with rising and falling contours
    lh_vowels = [vowel + "\u030c" for vowel in default_vowels]  # Caron: LH
    hl_vowels = [vowel + mark for vowel in default_vowels
                 for mark in ("\u0302", "\u0311")]  # Circumflex / inverted breve: HL
    mh_vowels = [vowel + "\u1dc4" for vowel in default_vowels]  # Macron-acute: MH
    lm_vowels = [vowel + "\u1dc5" for vowel in default_vowels]  # Grave-macron: LM
    ml_vowels = [vowel + "\u1dc6" for vowel in default_vowels]  # Macron-grave: ML
    hm_vowels = [vowel + "\u1dc7" for vowel in default_vowels]  # Acute-macron: HM

    # Three-part contour labels describe the order of low/high targets
    lhl_vowels = [vowel + "\u1dc8" for vowel in default_vowels]  # Grave-acute-grave: LHL
    hlh_vowels = [vowel + "\u1dc9" for vowel in default_vowels]  # Acute-grave-acute: HLH

    # Create an empty list for word-level tone patterns
    tones = []

    # Split the phrase into words
    words = tone_string.split()

    # Loop through each word
    for word in words:

        # Create an empty list for this word's tones
        word_tones = []

        # Group each base character with its combining marks
        characters = []
        for char in unicodedata.normalize("NFD", word):
            if unicodedata.combining(char) and characters:
                characters[-1] += char
            else:
                characters.append(char)

        # Loop through each character and its tone marks in the word
        for char in characters:

            # Check for level tones
            if char in h_vowels:
                word_tones.append("H")
            elif char in m_vowels:
                word_tones.append("M")
            elif char in l_vowels:
                word_tones.append("L")
            elif char in sh_vowels:
                word_tones.append("xH")
            elif char in sl_vowels:
                word_tones.append("xL")

            # Check for contour tones
            elif char in lh_vowels:
                word_tones.append("LH")
            elif char in hl_vowels:
                word_tones.append("HL")
            elif char in mh_vowels:
                word_tones.append("MH")
            elif char in lm_vowels:
                word_tones.append("LM")
            elif char in ml_vowels:
                word_tones.append("ML")
            elif char in hm_vowels:
                word_tones.append("HM")
            elif char in lhl_vowels:
                word_tones.append("LHL")
            elif char in hlh_vowels:
                word_tones.append("HLH")
            elif char[0] in default_vowels:
                raise ValueError(f'Unsupported vowel marking {char!r} in word {word!r}. Check its transcription.')

        # Ignore punctuation-only tokens but reject words that cannot be interpreted
        if not word_tones and any(char.isalnum() for char in word):
            raise ValueError(f'No supported vowels were found in word {word!r}. Check its transcription.')

        # Join this word's tones with hyphens
        tone_pattern = "-".join(word_tones)

        # Add this word's tone pattern to the list
        tones.append(tone_pattern)

    # Return one tone pattern per word
    return tones


# Function:     tokenize_phrase
# Inputs:       phrase | Kinande phrase to be tokenized (str)
# Outputs:      words | word tokens from the phrase (list)
# Description:  Splits a Kinande phrase into word tokens using spaces.

def tokenize_phrase(phrase):
    # Split the phrase into words using spaces
    words = phrase.split()

    # Return the list of word tokens
    return words


# Function:     validate_melodies
# Inputs:       words | word tokens from the Kinande phrase (list)
#               tones | word-level tone patterns for the Kinande phrase (list)
# Outputs:      is_valid | whether the words and tones match correctly (bool)
# Description:  Checks that every word has exactly one corresponding tone pattern.

def validate_melodies(words, tones):
    # Check whether the number of words matches the number of tone patterns
    is_valid = len(words) == len(tones)

    # If the counts do not match, print a helpful message
    if not is_valid:
        print("Word/tone mismatch:")
        print(f"  - Number of words: {len(words)}")
        print(f"  - Number of tone patterns: {len(tones)}")

    # Return whether the melodies are valid
    return is_valid


# Function:     make_word_sequence
# Inputs:       words | word tokens from the Kinande phrase (list)
#               tones | word-level tone patterns for the Kinande phrase (list)
# Outputs:      word_sequence | structured word and tone pattern data (list)
# Description:  Combines Kinande words and their tone patterns into a structured sequence.

def make_word_sequence(words, tones):
    # Reject mismatched inputs rather than silently dropping words through zip
    if len(words) != len(tones):
        raise ValueError('Each word must have one tone pattern.')
    # Create an empty list to store word objects
    word_sequence = []

    # Loop through each word and its matching tone pattern
    for i, (word, tone_pattern) in enumerate(zip(words, tones)):

        # Punctuation has no tones and must not consume a detected note
        if not tone_pattern:
            if any(char.isalnum() for char in word):
                raise ValueError(f'No tone pattern was provided for word {word!r}.')
            continue

        # Split the word-level tone pattern into individual tones
        tone_list = tone_pattern.split("-")
        if any(not tone for tone in tone_list):
            raise ValueError(f'Invalid tone pattern for word {word!r}.')

        # Store the word and its tone information together
        word_data = {
            "index": i,
            "word": word,
            "tone_pattern": tone_pattern,
            "tones": tone_list
        }

        # Add this word object to the sequence
        word_sequence.append(word_data)

    # Return the structured word sequence
    return word_sequence
