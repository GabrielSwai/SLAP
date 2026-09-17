# =====================================================================================
# Surrogate Language Aligner
#
# Parse Kinande phrases and construct word-level tone sequences.
# =====================================================================================


# Function:     parse_tones
# Inputs:       tone_string | spoken phrase (str)
# Outputs:      tones | parsed word-level tone patterns (list)
# Description:  Converts a phrase like "Tukándisyá tasáta kwȇ?" into a list of tone patterns like ["L-H-L-H", "L-H-L", "HL"].

def parse_tones(tone_string):
    # Vowels with high tone
    h_vowels = ["á", "é", "í", "ó", "ú", "Á", "É", "Í", "Ó", "Ú"]

    # Vowels with low tone
    l_vowels = ["a", "e", "i", "o", "u", "A", "E", "I", "O", "U"]

    # Vowels with falling tone
    f_vowels = ["â", "ê", "î", "ô", "û", "ȃ", "ȇ", "ȋ", "ȏ", "ȗ",
                "Â", "Ê", "Î", "Ô", "Û", "Ȃ", "Ȇ", "Ȋ", "Ȏ", "Ȗ"]

    # Create an empty list for word-level tone patterns
    tones = []

    # Split the phrase into words
    words = tone_string.split()

    # Loop through each word
    for word in words:

        # Create an empty list for this word's tones
        word_tones = []

        # Loop through each character in the word
        for char in word:

            # Check for high-toned vowels
            if char in h_vowels:
                word_tones.append("H")

            # Check for low-toned vowels
            elif char in l_vowels:
                word_tones.append("L")

            # Check for falling-toned vowels
            elif char in f_vowels:
                word_tones.append("HL")

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
    # Create an empty list to store word objects
    word_sequence = []

    # Loop through each word and its matching tone pattern
    for i, (word, tone_pattern) in enumerate(zip(words, tones)):

        # Split the word-level tone pattern into individual tones
        tone_list = tone_pattern.split("-")

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
