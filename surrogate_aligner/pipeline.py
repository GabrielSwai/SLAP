# =====================================================================================
# Surrogate Language Aligner
#
# Coordinate audio analysis, alignment, and annotation export.
# =====================================================================================

from .audio import load_audio, extract_audio_segment
from .annotations import load_elan, get_elan_segments, add_alignment, save_elan
from .detection import detect_note_onsets, make_note_intervals
from .features import extract_pitch, extract_shape
from .classification import classify_pitches
from .tones import tokenize_phrase, parse_tones, validate_melodies, make_word_sequence
from .aligner import (
    make_surrogate_sequence,
    align_sequences,
    flag_mismatches,
    calculate_confidence,
)


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
