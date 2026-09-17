# =====================================================================================
# Surrogate Language Aligner
#
# Align spoken and surrogate tone sequences.
# =====================================================================================

import numpy as np


# Function:     make_surrogate_sequence
# Inputs:       intervals | start and end times for each detected note (list)
#               surrogate_tones | H/L tone labels for each detected note (list)
# Outputs:      surrogate_sequence | structured surrogate note data (list)
# Description:  Combines note intervals and H/L tone labels into a structured surrogate sequence.

def make_surrogate_sequence(intervals, surrogate_tones):
    # Create an empty list to store surrogate note objects
    surrogate_sequence = []

    # Loop through each interval and its matching surrogate tone
    for i, (interval, tone) in enumerate(zip(intervals, surrogate_tones)):

        # Store the note interval and tone together
        note_data = {
            "index": i,
            "start": interval["start"],
            "end": interval["end"],
            "tone": tone
        }

        # Add this note object to the surrogate sequence
        surrogate_sequence.append(note_data)

    # Return the structured surrogate sequence
    return surrogate_sequence


# Function:     score_alignment
# Inputs:       spoken_tone | tone from the Kinande word sequence (str)
#               surrogate_tone | tone from the surrogate note sequence (str)
# Outputs:      score | numerical alignment score for the tone pair (int or float)
# Description:  Scores a tone match, mismatch, or gap during sequence alignment.

def score_alignment(spoken_tone, surrogate_tone):
    # If either tone is missing, treat it as a gap
    if spoken_tone is None or surrogate_tone is None:
        score = -2

    # Give a positive score for an exact tone match
    elif spoken_tone == surrogate_tone:
        score = 2

    # Give a smaller penalty for a mismatch
    else:
        score = -1

    # Return the alignment score
    return score


# Function:     align_sequences
# Inputs:       spoken_sequence | structured Kinande word/tone sequence (list)
#               surrogate_sequence | structured surrogate note sequence (list)
# Outputs:      alignment | optimal alignment between Kinande words and surrogate notes (list)
# Description:  Aligns the Kinande tone sequence with the surrogate tone sequence using a scoring algorithm.

def align_sequences(spoken_sequence, surrogate_sequence):
    # Flatten the spoken word sequence into individual tone objects
    spoken_tones = []
    for word_data in spoken_sequence:

        # Loop through each tone in this word
        for tone_index, tone in enumerate(word_data["tones"]):

            # Store the tone with its word information
            spoken_tones.append({
                "word_index": word_data["index"],
                "word": word_data["word"],
                "tone_index": tone_index,
                "tone": tone
            })

    # Flatten the surrogate sequence into individual tone objects
    surrogate_tones = []
    for note_data in surrogate_sequence:

        # Store the surrogate tone with its timing information
        surrogate_tones.append({
            "note_index": note_data["index"],
            "start": note_data["start"],
            "end": note_data["end"],
            "tone": note_data["tone"]
        })

    # Get sequence lengths
    n = len(spoken_tones)
    m = len(surrogate_tones)

    # Create score matrix
    score_matrix = np.zeros((n + 1, m + 1))

    # Create backpointer matrix
    backpointer_matrix = [[None for _ in range(m + 1)] for _ in range(n + 1)]

    # Fill first column with gap penalties
    for i in range(1, n + 1):
        score_matrix[i][0] = score_matrix[i - 1][0] + score_alignment(spoken_tones[i - 1]["tone"], None)
        backpointer_matrix[i][0] = "up"

    # Fill first row with gap penalties
    for j in range(1, m + 1):
        score_matrix[0][j] = score_matrix[0][j - 1] + score_alignment(None, surrogate_tones[j - 1]["tone"])
        backpointer_matrix[0][j] = "left"

    # Fill the rest of the matrix
    for i in range(1, n + 1):

        # Loop through surrogate tones
        for j in range(1, m + 1):

            # Score a spoken tone aligned to a surrogate tone
            diagonal_score = score_matrix[i - 1][j - 1] + score_alignment(
                spoken_tones[i - 1]["tone"],
                surrogate_tones[j - 1]["tone"]
            )

            # Score a spoken tone aligned to a gap
            up_score = score_matrix[i - 1][j] + score_alignment(
                spoken_tones[i - 1]["tone"],
                None
            )

            # Check whether an extra surrogate note would be placed between words
            if i == 0 or i == n:
                at_word_boundary = True
            else:
                previous_word_index = spoken_tones[i - 1]["word_index"]
                next_word_index = spoken_tones[i]["word_index"]
                at_word_boundary = previous_word_index != next_word_index

            # Only allow surrogate-only gaps between words
            if at_word_boundary:
                left_score = score_matrix[i][j - 1] + score_alignment(
                    None,
                    surrogate_tones[j - 1]["tone"]
                )
            else:
                left_score = -999999

            # Choose the best score
            best_score = max(diagonal_score, up_score, left_score)

            # Store the best score
            score_matrix[i][j] = best_score

            # Store the direction that produced the best score
            if best_score == diagonal_score:
                backpointer_matrix[i][j] = "diagonal"
            elif best_score == up_score:
                backpointer_matrix[i][j] = "up"
            else:
                backpointer_matrix[i][j] = "left"

    # Create an empty alignment list
    alignment = []

    # Start traceback from bottom-right corner
    i = n
    j = m

    # Trace back until both sequences are exhausted
    while i > 0 or j > 0:

        # Get traceback direction
        direction = backpointer_matrix[i][j]

        # Match/mismatch case
        if direction == "diagonal":

            # Get current spoken tone
            spoken = spoken_tones[i - 1]

            # Get current surrogate tone
            surrogate = surrogate_tones[j - 1]

            # Add aligned pair
            alignment.append({
                "spoken": spoken,
                "surrogate": surrogate,
                "spoken_tone": spoken["tone"],
                "surrogate_tone": surrogate["tone"],
                "start": surrogate["start"],
                "end": surrogate["end"],
                "score": score_alignment(spoken["tone"], surrogate["tone"])
            })

            # Move diagonally
            i -= 1
            j -= 1

        # Spoken tone aligned to gap
        elif direction == "up":

            # Get current spoken tone
            spoken = spoken_tones[i - 1]

            # Add gap alignment
            alignment.append({
                "spoken": spoken,
                "surrogate": None,
                "spoken_tone": spoken["tone"],
                "surrogate_tone": None,
                "start": None,
                "end": None,
                "score": score_alignment(spoken["tone"], None)
            })

            # Move up
            i -= 1

        # Surrogate tone aligned to gap
        elif direction == "left":

            # Get current surrogate tone
            surrogate = surrogate_tones[j - 1]

            # Add gap alignment
            alignment.append({
                "spoken": None,
                "surrogate": surrogate,
                "spoken_tone": None,
                "surrogate_tone": surrogate["tone"],
                "start": surrogate["start"],
                "end": surrogate["end"],
                "score": score_alignment(None, surrogate["tone"])
            })

            # Move left
            j -= 1

        # Safety fallback
        else:
            break

    # Reverse alignment because traceback builds it backwards
    alignment.reverse()

    # Return the final alignment
    return alignment


# Function:     flag_mismatches
# Inputs:       alignment | alignment between Kinande words and surrogate notes (list)
# Outputs:      flagged_alignment | alignment with mismatches marked (list)
# Description:  Marks places where the Kinande tone pattern and surrogate tone pattern do not match cleanly.

def flag_mismatches(alignment):
    # Create an empty list to store flagged alignment items
    flagged_alignment = []

    # Loop through each item in the alignment
    for item in alignment:

        # Make a copy so we do not modify the original item directly
        flagged_item = item.copy()

        # Get the spoken tone
        spoken_tone = item["spoken_tone"]

        # Get the surrogate tone
        surrogate_tone = item["surrogate_tone"]

        # If either item is missing, mark it as a gap
        if spoken_tone is None or surrogate_tone is None:
            flagged_item["match_status"] = "gap"
            flagged_item["is_match"] = False

        # If the tones match exactly, mark it as a match
        elif spoken_tone == surrogate_tone:
            flagged_item["match_status"] = "match"
            flagged_item["is_match"] = True

        # Otherwise, mark it as a mismatch
        else:
            flagged_item["match_status"] = "mismatch"
            flagged_item["is_match"] = False

        # Add the flagged item to the output list
        flagged_alignment.append(flagged_item)

    # Return the flagged alignment
    return flagged_alignment


# Function:     calculate_confidence
# Inputs:       alignment | alignment between Kinande words and surrogate notes (list)
# Outputs:      confidence | confidence score for the alignment (float)
# Description:  Calculates an overall confidence score based on matches, mismatches, and gaps.

def calculate_confidence(alignment):
    # If there is no alignment, return 0 confidence
    if len(alignment) == 0:
        return 0.0

    # Initialize exact match count
    matches = 0

    # Initialize mismatch count
    mismatches = 0

    # Initialize gap count
    gaps = 0

    # Loop through each aligned item
    for item in alignment:

        # Get the spoken and surrogate tones
        spoken_tone = item["spoken_tone"]
        surrogate_tone = item["surrogate_tone"]

        # Count gaps
        if spoken_tone is None or surrogate_tone is None:
            gaps += 1

        # Count exact matches
        elif spoken_tone == surrogate_tone:
            matches += 1

        # Count mismatches
        else:
            mismatches += 1

    # Count total aligned items
    total = matches + mismatches + gaps

    # Avoid division by zero
    if total == 0:
        return 0.0

    # Calculate confidence as the proportion of exact matches
    confidence = matches / total

    # Return the confidence score
    return confidence


# Function:     group_alignment
# Inputs:       alignment | alignment between Kinande words and surrogate notes (list)
# Outputs:      grouped_alignment | alignment between Kinande words and surrogate notes group by word (list)
# Description:  Groups aligned Kinande words and surrogate notes by word.

def group_alignment(alignment):
    # Create an empty list for word-level grouped alignment
    grouped_alignment = []

    # Keep track of the current word group
    current_group = None

    # Loop through each tone-level alignment item
    for item in alignment:

        # If this is an extra surrogate note with no spoken tone, output it as an insertion
        if item["spoken"] is None:

            # Save the previous word group first
            if current_group is not None:
                grouped_alignment.append(current_group)
                current_group = None

            # Create an insertion group for the extra surrogate note
            insertion_group = {
                "segment_index": item.get("segment_index"),
                "segment_start": item.get("segment_start"),
                "segment_end": item.get("segment_end"),
                "word_index": None,
                "word": "",
                "spoken_tones": [],
                "surrogate_tones": [],
                "start": item["start"],
                "end": item["end"],
                "items": [item]
            }

            # Add the surrogate tone if it exists
            if item["surrogate_tone"] is not None:
                insertion_group["surrogate_tones"].append(item["surrogate_tone"])

            # Add empty spoken pattern
            insertion_group["spoken_tone_pattern"] = ""

            # Add surrogate pattern
            insertion_group["surrogate_tone_pattern"] = "-".join(insertion_group["surrogate_tones"])

            # Add insertion group to output
            grouped_alignment.append(insertion_group)

            # Move to next item
            continue

        # Get the word index for this tone
        segment_index = item.get("segment_index")
        word_index = item["spoken"]["word_index"]

        # Start a new group when we see a new word
        if current_group is None or current_group["word_index"] != word_index or current_group["segment_index"] != segment_index:

            # Save the old group before starting a new one
            if current_group is not None:
                grouped_alignment.append(current_group)

            # Create a new word-level group
            current_group = {
                "segment_index": segment_index,
                "segment_start": item.get("segment_start"),
                "segment_end": item.get("segment_end"),
                "word_index": word_index,
                "word": item["spoken"]["word"],
                "spoken_tones": [],
                "surrogate_tones": [],
                "start": None,
                "end": None,
                "items": []
            }

        # Add this tone-level item to the current group
        current_group["items"].append(item)

        # Add spoken tone if it exists
        if item["spoken_tone"] is not None:
            current_group["spoken_tones"].append(item["spoken_tone"])

        # Add surrogate tone if it exists
        if item["surrogate_tone"] is not None:
            current_group["surrogate_tones"].append(item["surrogate_tone"])

        # Update start time if this item has timing
        if item["start"] is not None:
            if current_group["start"] is None:
                current_group["start"] = item["start"]
            else:
                current_group["start"] = min(current_group["start"], item["start"])

        # Update end time if this item has timing
        if item["end"] is not None:
            if current_group["end"] is None:
                current_group["end"] = item["end"]
            else:
                current_group["end"] = max(current_group["end"], item["end"])

    # Add the final group
    if current_group is not None:
        grouped_alignment.append(current_group)

    # Add joined tone-pattern strings
    for group in grouped_alignment:

        # If there are spoken tones, join them into one pattern
        if len(group["spoken_tones"]) > 0:
            group["spoken_tone_pattern"] = "-".join(group["spoken_tones"])

        # Otherwise, use an empty string
        else:
            group["spoken_tone_pattern"] = ""

        # If there are surrogate tones, join them into one pattern
        if len(group["surrogate_tones"]) > 0:
            group["surrogate_tone_pattern"] = "-".join(group["surrogate_tones"])

        # Otherwise, use an empty string
        else:
            group["surrogate_tone_pattern"] = ""

    # Return word-level grouped alignment
    return grouped_alignment
