# =====================================================================================
# Surrogate Language Aligner
# Gabriel Swai (gabriel.a.swai@gmail.com)
# Last modification: 2026/09/14
#
# This project is a semi-automatic Python tool for aligning spoken tone
# patterns with corresponding drummed musical surrogate patterns.
# =====================================================================================

from pathlib import Path
import librosa
import numpy as np
import pympi
import parselmouth


# Constants

from surrogate_aligner.config import (
    AUDIO_PATH,
    ELAN_INPUT_PATH,
    ELAN_OUTPUT_PATH,
    INPUT_TIER,
    OUTPUT_DIR,
    OUTPUT_TIERS,
)


# Function:     load_elan
# Inputs:       elan_path | file path of ELAN file to be loaded (Path)
# Outputs:      eaf | loaded ELAN file object (Eaf)
# Description:  Loads an ELAN .eaf file so that its annotation tiers can be read/modified.

def load_elan(elan_path):
    # Convert Path to string so pympi can read it
    elan_path = str(elan_path)

    # Load the ELAN file
    eaf = pympi.Elan.Eaf(elan_path)

    # Return the loaded ELAN object
    return eaf


# Function:     get_elan_segments
# Inputs:       eaf | loaded ELAN file object
#               tier_name | name of ELAN tier to extract annotations from (str)
# Outputs:      segments | list of annotation intervals and labels from the specified tier (list)
# Description:  Extracts start times, end times, and annotation values from a given ELAN tier.

def get_elan_segments(eaf, tier_name):
    # Get all annotations from the specified ELAN tier
    annotations = eaf.get_annotation_data_for_tier(tier_name)

    # Create an empty list to store the cleaned segment data
    segments = []

    # Loop through each annotation in the tier
    for start_time, end_time, label in annotations:

        # Store each annotation as a dictionary
        segment = {
            "start": start_time / 1000,
            "end": end_time / 1000,
            "label": label
        }

        # Add the segment to the list
        segments.append(segment)

    # Return the list of extracted segments
    return segments


# Function:     detect_note_onsets
# Inputs:       y_segment | extracted audio segment (NumPy array)
#               sr | sampling rate of the audio segment (int)
# Outputs:      onset_times | detected onset times of notes in seconds (list)
# Description:  Detects the approximate start times of individual surrogate notes in the audio segment.

def detect_note_onsets(y_segment, sr):
    # Detect onset frames in the audio segment
    onset_frames = librosa.onset.onset_detect(
        y=y_segment,
        sr=sr,
        units="frames",
        backtrack=True,
        pre_max=10,
        post_max=10,
        pre_avg=20,
        post_avg=20,
        delta=0.2,
        wait=8
    )

    # Convert onset frames into times in seconds
    onset_times = librosa.frames_to_time(onset_frames, sr=sr)

    # Convert NumPy array to a regular Python list
    onset_times = onset_times.tolist()

    # Return the detected onset times
    return onset_times


# Function:     make_note_intervals
# Inputs:       onset_times | detected onset times of notes in seconds (list)
#               segment_start | start time of the full segment in seconds (float)
#               segment_end | end time of the full segment in seconds (float)
# Outputs:      intervals | start and end times for each detected note (list)
# Description:  Converts note onset times into note intervals with start and end times.

def make_note_intervals(onset_times, segment_start, segment_end):
    # Initialize an empty list to store note intervals
    intervals = []

    # Convert relative onset times to absolute times
    absolute_onsets = [segment_start + onset for onset in onset_times]

    # If no onsets were detected, return an empty list
    if len(absolute_onsets) == 0:
        return intervals

    # Loop through each detected onset
    for i in range(len(absolute_onsets)):

        # The note starts at the current onset
        start = absolute_onsets[i]

        # The note ends at the next onset, unless this is the last note
        if i < len(absolute_onsets) - 1:
            end = absolute_onsets[i + 1]

        # The final note ends at the end of the full segment
        else:
            end = segment_end

        # Store the note interval
        intervals.append({
            "start": start,
            "end": end
        })

    # Return the list of note intervals
    return intervals


# Function:     extract_pitch
# Inputs:       y_segment | extracted audio segment (NumPy array)
#               sr | sampling rate of the audio segment (int)
#               intervals | start and end times for each detected note (list)
#               low_min | 
# Outputs:      pitch_features | pitch-related feature values for each note interval (list)
# Description:  Extracts acoustic pitch features from each detected note interval using magnitude spectrum.

def extract_pitch(y_segment, sr, intervals, segment_start):
    # Create an empty list to store one pitch value per note
    pitch_features = []

    # Convert NumPy audio into a Parselmouth Sound object
    sound = parselmouth.Sound(y_segment, sampling_frequency=sr)

    # Run Praat's pitch tracker
    pitch = sound.to_pitch_ac(
        time_step=None,
        pitch_floor=50,
        max_number_of_candidates=15,
        very_accurate=False,
        silence_threshold=0.02,
        voicing_threshold=0.1,
        octave_cost=0.15,
        octave_jump_cost=0.5,
        voiced_unvoiced_cost=0.14,
        pitch_ceiling=800
    )

    # Loop through each note interval
    for interval in intervals:

        # Convert absolute times to segment-relative times
        relative_start = interval["start"] - segment_start
        relative_end = interval["end"] - segment_start

        # Get note duration
        note_duration = relative_end - relative_start

        # Skip the noisy attack
        analysis_start = relative_start + 0.3 * note_duration

        # Avoid the very end of the decay
        analysis_end = relative_start + 0.60 * note_duration

        # Get pitch values inside this note interval
        times = pitch.xs()
        values = pitch.selected_array["frequency"]

        # Keep only pitch values inside this note
        mask = (times >= analysis_start) & (times <= analysis_end)

        # Remove unvoiced frames, which Praat marks as 0
        note_pitches = values[mask]
        note_pitches = note_pitches[note_pitches > 0]

        # If no pitch was detected, store 0
        if len(note_pitches) == 0:
            pitch_features.append(0)
            continue

        # Use the median pitch for stability
        note_pitch = float(np.median(note_pitches))

        # Store one pitch value for this note
        pitch_features.append(note_pitch)

    # Return one pitch value per note interval
    return pitch_features


# Function:     extract_shape
# Inputs:       y_segment | extracted audio segment (NumPy array)
#               sr | sampling rate of the audio segment (int)
#               intervals | start and end times for each detected note (list)
#               segment_start | start time of the full segment in seconds (float)
# Outputs:      shape_features | shortness/decay score for each detected note (list)
# Description:  Extracts note-shape features based on how quickly each strike decays.

def extract_shape(
    y_segment,
    sr,
    intervals,
    segment_start,
    shape_window_seconds=0.1,
    frame_ms=8,
    hop_ms=2,
    threshold_ratio=0.52,
    max_tail_time=0.25
):

    # Create an empty list to store shape scores
    shape_features = []

    # Convert frame size from milliseconds to samples
    frame_length = max(1, int((frame_ms / 1000) * sr))

    # Convert hop size from milliseconds to samples
    hop_length = max(1, int((hop_ms / 1000) * sr))

    # Loop through each note interval
    for interval in intervals:

        # Convert absolute start time to segment-relative time
        relative_start = interval["start"] - segment_start

        # Convert start time to samples
        start_sample = int(relative_start * sr)

        # Use a fixed window after onset
        end_sample = min(
            start_sample + int(shape_window_seconds * sr),
            len(y_segment)
        )

        # Extract note window
        y_note = y_segment[start_sample:end_sample]

        # Skip empty notes
        if len(y_note) == 0:
            shape_features.append(0)
            continue

        # Compute RMS envelope
        rms = librosa.feature.rms(
            y=y_note,
            frame_length=frame_length,
            hop_length=hop_length
        )[0]

        # Skip empty RMS
        if len(rms) == 0:
            shape_features.append(0)
            continue

        # Get peak RMS
        peak = np.max(rms)

        # Avoid division by zero
        if peak == 0:
            shape_features.append(0)
            continue

        # Normalize RMS by peak
        rms = rms / peak

        # Search for peak only near the beginning
        peak_search_frames = max(1, int(0.05 / (hop_ms / 1000)))

        # Prevent search window from exceeding RMS length
        peak_search_frames = min(peak_search_frames, len(rms))

        # Find peak index in early part
        peak_index = int(np.argmax(rms[:peak_search_frames]))

        # Keep decay after peak
        decay = rms[peak_index:]

        # Skip empty decay
        if len(decay) == 0:
            shape_features.append(0)
            continue

        # Find frames still above threshold
        active = np.where(decay >= threshold_ratio)[0]

        # If no active frames, tail time is zero
        if len(active) == 0:
            tail_time = 0

        # Otherwise get last active frame time
        else:
            tail_time = (active[-1] * hop_length) / sr

        # Convert tail time to H-like shortness score
        tail_shortness = 1.0 - (tail_time / max_tail_time)

        # Clamp to 0-1
        tail_shortness = max(0, min(tail_shortness, 1))

        # Define early region after peak
        early_end = min(len(decay), max(2, int(0.05 / (hop_ms / 1000))))

        # Define late region after early region
        late_start = min(len(decay), max(2, int(0.10 / (hop_ms / 1000))))

        # Compute early energy
        early_energy = np.mean(decay[:early_end])

        # Compute late energy
        if late_start >= len(decay):
            late_energy = 0
        else:
            late_energy = np.mean(decay[late_start:])

        # Lower tail energy is more H-like
        tail_energy_ratio = late_energy / (early_energy + 1e-9)

        # Convert to shortness score
        energy_shortness = 1.0 - tail_energy_ratio

        # Clamp to 0-1
        energy_shortness = max(0, min(energy_shortness, 1))

        # Estimate decay slope on log RMS
        x = np.arange(len(decay))

        # Avoid log(0)
        y = np.log(decay + 1e-6)

        # Fit a simple line to log-decay
        if len(x) >= 2:
            slope = np.polyfit(x, y, 1)[0]
        else:
            slope = 0

        # More negative slope means faster decay
        slope_shortness = min(1, max(0, -slope * 10))

        # Combine cues into one shape score
        shape_score = (
            0.45 * tail_shortness
            + 0.35 * energy_shortness
            + 0.20 * slope_shortness
        )

        # Store shape score
        shape_features.append(float(shape_score))

    # Return one shape score per note
    return shape_features


# Function:     classify_pitches
# Inputs:       pitch_features | pitch-related feature values for each note interval (list)
# Outputs:      surrogate_tones | H/L tone labels for each detected note (list)
# Description:  Classifies each note as high or low based on its extracted pitch feature and strike shape.

def classify_pitches(pitch_features, shape_features):

    # If there are no pitch features, return an empty list
    if len(pitch_features) == 0:
        return []

    # If no shape features were given, use zeros
    if shape_features is None:
        shape_features = [0] * len(pitch_features)

    # Make sure both lists match
    if len(pitch_features) != len(shape_features):
        raise ValueError("pitch_features and shape_features must have the same length.")

    # Convert pitches to NumPy array
    pitches = np.array(pitch_features, dtype=float)

    # Convert shape features to NumPy array
    shapes = np.array(shape_features, dtype=float)

    # Normalize shape features
    if np.max(shapes) == np.min(shapes):
        shape_norm = np.zeros_like(shapes)
    else:
        shape_norm = (shapes - np.min(shapes)) / (np.max(shapes) - np.min(shapes))

    # Keep only valid pitch values
    valid_pitches = pitches[pitches > 0]

    # If no valid pitches exist, classify by shape only
    if len(valid_pitches) == 0:
        boundary = np.median(shape_norm)
        return ["H" if s >= boundary else "L" for s in shape_norm]

    # Initialize centers
    pitch_boundary = 120.0

    # Create empty list for labels
    surrogate_tones = []

    # Classify each note
    for pitch, shape in zip(pitches, shape_norm):
        # If pitch exists, classify using pitch only
        if pitch > 0:
            # Compare pitch directly to boundary
            if pitch >= pitch_boundary:
                surrogate_tones.append("H")
            else:
                surrogate_tones.append("L")

        # If pitch failed, assume H, but let shape override if it is strongly L-like
        else:
            # Very low shortness means long/ringy tail, so mark as L
            if shape <= 0.4:
                surrogate_tones.append("L")

            # Otherwise default to H
            else:
                surrogate_tones.append("H")

    # Return H/L labels
    return surrogate_tones


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


# Function:     clear_tier
# Inputs:       eaf | loaded ELAN file object
#               tier_name | name of ELAN tier to be cleared (str)
# Outputs:      eaf | modified ELAN file object
# Description:  Clears annotations on a tier of an ELAN file.

def clear_tier(eaf, tier_name):
    # Get all existing annotations from this tier
    annotations = eaf.get_annotation_data_for_tier(tier_name)

    # Loop through existing annotations
    for start_ms, end_ms, value in annotations:

        # Remove this annotation from the tier
        eaf.remove_annotation(tier_name, start_ms)

    # Return modified ELAN object
    return eaf


# Function:     add_alignment
# Inputs:       eaf | loaded ELAN file object
#               alignment | alignment between Kinande words and surrogate notes (list)
#               tier_names | name of ELAN tiers where alignment should be added (dict)
# Outputs:      eaf | modified ELAN file object
# Description:  Adds the generated word-to-surrogate alignment to a specified ELAN tier.

def add_alignment(eaf, alignment, tier_names):
    # Group tone-level alignment into word-level alignment
    grouped_alignment = group_alignment(alignment)

    # Get existing tier names
    word_tier = tier_names["words"]
    spoken_tone_tier = tier_names["spoken_tones"]
    surrogate_tone_tier = tier_names["surrogate_tones"]

    # Add the tiers if they don't already exist
    if word_tier not in eaf.get_tier_names():
        eaf.add_tier(word_tier)
    if spoken_tone_tier not in eaf.get_tier_names():
        eaf.add_tier(spoken_tone_tier)
    if surrogate_tone_tier not in eaf.get_tier_names():
        eaf.add_tier(surrogate_tone_tier)

    # Clear existing annotations
    clear_tier(eaf, word_tier)
    clear_tier(eaf, spoken_tone_tier)
    clear_tier(eaf, surrogate_tone_tier)

    # Loop through each word-level group
    for group in grouped_alignment:

        # Skip groups with no timing
        if group["start"] is None or group["end"] is None:
            continue

        # Keep output annotations inside the original input annotation
        segment_start = group.get("segment_start")
        segment_end = group.get("segment_end")

        # Clamp start/end to the segment boundaries
        start = group["start"]
        end = group["end"]

        if segment_start is not None:
            start = max(start, segment_start)

        if segment_end is not None:
            end = min(end, segment_end)

        # Skip invalid intervals after clamping
        if end <= start:
            continue

        # Convert start/end from seconds to milliseconds
        start_ms = int(round(start * 1000))
        end_ms = int(round(end * 1000))

        # Get word text
        word = group["word"]

        # Get grouped spoken tone pattern
        spoken_tone_pattern = group["spoken_tone_pattern"]

        # Get grouped surrogate tone pattern
        surrogate_tone_pattern = group["surrogate_tone_pattern"]

        # Add word annotation
        eaf.add_annotation(word_tier, start_ms, end_ms, word)

        # Add spoken tone annotation
        eaf.add_annotation(spoken_tone_tier, start_ms, end_ms, spoken_tone_pattern)

        # Add surrogate tone annotation
        eaf.add_annotation(surrogate_tone_tier, start_ms, end_ms, surrogate_tone_pattern)

    # Return modified ELAN object
    return eaf


# Function:     save_elan
# Inputs:       eaf | modified ELAN file object
#               output_path | file path where modified ELAN file should be saved (Path)
# Outputs:      None
# Description:  Saves the modified ELAN file to disk.

def save_elan(eaf, output_path):
    # Make sure output path is a Path object to avoid an exception
    output_path = Path(output_path)

    # Make sure the output folder exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Save the modified ELAN file
    eaf.to_file(str(output_path))

    # Return nothing
    return None


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


# Function:     run_pipeline
# Inputs:       config | dictionary containing file paths, tier names, and settings (dict)
# Outputs:      full_alignment | final alignment between Kinande words and surrogate notes (list)
#               confidence | confidence score for the final alignment (float)
# Description:  Runs the full alignment workflow from input loading to output file creation.

def run_pipeline(config):
    # Make sure output folder exists
    config["output_dir"].mkdir(exist_ok=True)

    # Load audio
    print("Loading audio...")
    y, sr, d = load_audio(config["audio_path"])

    # Load ELAN file
    print("Loading ELAN file...")
    eaf = load_elan(config["elan_input_path"])

    # Get phrase/drumming segments from the input tier
    print("Getting ELAN segments...")
    segments = get_elan_segments(eaf, config["input_tier"])

    # Create one big alignment list for all segments
    full_alignment = []

    # Process each annotated phrase/drumming segment
    print("Processing segments...")
    for i, segment in enumerate(segments):

        # Get segment times
        start_time = segment["start"]
        end_time = segment["end"]

        # Get Kinande phrase from ELAN label
        phrase = segment["label"]

        # Print progress
        print(f"  - {i + 1}/{len(segments)}:")
        print(f"    - Phrase: {phrase}")
        print(f"    - Time: {start_time:.2f}–{end_time:.2f}")

        # Extract this audio segment
        y_segment = extract_audio_segment(y, sr, start_time, end_time)

        # Detect note onsets
        onset_times = detect_note_onsets(y_segment, sr)

        # Convert onsets into note intervals
        intervals = make_note_intervals(onset_times, start_time, end_time)

        # Extract pitch features
        pitch_features = extract_pitch(y_segment, sr, intervals, start_time)

        # Extract shape features
        shape_features = extract_shape(y_segment, sr, intervals, start_time)

        # Classify surrogate notes as H/L
        surrogate_tones = classify_pitches(pitch_features, shape_features)

        # Tokenize Kinande phrase into words
        words = tokenize_phrase(phrase)

        # Parse Kinande phrase into word-level tone patterns
        tones = parse_tones(phrase)

        # Check that each word has a tone pattern
        is_valid = validate_melodies(words, tones)

        # Skip this segment if the word/tone parsing failed
        if not is_valid:
            print("  - Skipping segment because word/tone counts do not match.")
            continue

        # Build structured word sequence
        word_sequence = make_word_sequence(words, tones)

        # Build structured surrogate sequence
        surrogate_sequence = make_surrogate_sequence(intervals, surrogate_tones)

        # Align spoken tones to surrogate tones
        alignment = align_sequences(word_sequence, surrogate_sequence)

        # Flag matches, mismatches, and gaps
        flagged_alignment = flag_mismatches(alignment)

        # Add segment information so words from different segments don't group together
        for item in flagged_alignment:
            item["segment_index"] = i
            item["segment_start"] = start_time
            item["segment_end"] = end_time
            item["phrase"] = phrase

        # Add this segment's alignment to the full alignment
        full_alignment.extend(flagged_alignment)

    # Calculate confidence across all aligned segments
    confidence = calculate_confidence(full_alignment)

    # Add alignment tiers to ELAN
    print("Adding alignment to ELAN...")
    eaf = add_alignment(eaf, full_alignment, config["output_tiers"])

    # Save modified ELAN file
    print("Saving ELAN file...")
    save_elan(eaf, config["elan_output_path"])

    # Return final alignment and confidence
    return full_alignment, confidence


# Function:     main
# Inputs:       None
# Outputs:      None
# Description:  Main project pipeline.

def main():
    # Print project header
    print("=== SURROGATE LANGUAGE ALIGNER ===\n")

    # Store pipeline settings in one config dictionary
    config = {
        "audio_path": AUDIO_PATH,
        "elan_input_path": ELAN_INPUT_PATH,
        "input_tier": INPUT_TIER,
        "output_dir": OUTPUT_DIR,
        "output_tiers": OUTPUT_TIERS,
        "elan_output_path": ELAN_OUTPUT_PATH
    }

    # Run the full pipeline
    alignment, confidence = run_pipeline(config)

    # Print final summary
    print("\n=== Processing Complete ===")
    print(f"  - Aligned items: {len(alignment)}")
    print(f"  - Confidence: {confidence:.2f}")
    print(f"  - ELAN saved to: {config['elan_output_path']}")
    print()


if __name__ == "__main__":
    main()