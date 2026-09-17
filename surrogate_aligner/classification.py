# =====================================================================================
# Surrogate Language Aligner
#
# Classify acoustic features as high or low tones.
# =====================================================================================

import numpy as np


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
