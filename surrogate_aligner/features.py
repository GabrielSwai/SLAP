# =====================================================================================
# Surrogate Language Aligner
#
# Extract pitch and decay features from audio.
# =====================================================================================

import librosa
import numpy as np
import parselmouth


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
