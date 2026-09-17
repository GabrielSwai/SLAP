# =====================================================================================
# Surrogate Language Aligner
#
# Detect note onsets and construct note intervals.
# =====================================================================================

import librosa


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
