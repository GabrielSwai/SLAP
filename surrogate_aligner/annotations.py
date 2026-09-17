# =====================================================================================
# Surrogate Language Aligner
#
# Read and write ELAN annotations.
# =====================================================================================

from pathlib import Path
import pympi

from .aligner import group_alignment


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
