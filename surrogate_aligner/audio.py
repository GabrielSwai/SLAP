# =====================================================================================
# Surrogate Language Aligner: Audio Processing
#
# This module loads audio recordings and extracts selected audio segments.
# =====================================================================================

import librosa


# Function:     load_audio
# Inputs:       audio_path | file path of audio file to be loaded (Path)
# Outputs:      y | audio waveform (NumPy array)
#               sr | sampling rate of the audio waveform, y (int)
#               d | duration of the audio (float)
# Description:  Loads an audio file using librosa.

def load_audio(audio_path):
    # Load the audio file with its original sampling rate
    y, sr = librosa.load(audio_path, sr=None)

    # Get the duration of the audio file in seconds
    d = librosa.get_duration(y=y, sr=sr)

    # Return the waveform, sampling rate, and duration
    return y, sr, d


# Function:     extract_audio_segment
# Inputs:       y | audio waveform (NumPy array)
#               sr | sampling rate of the audio segment (int)
#               start_time | start time of the segment in seconds (float)
#               end_time | end time of the segment in seconds (float)
# Outputs:      y_segment | extracted audio segment (NumPy array)
# Description:  Extracts a smaller audio segment using start and end times.

def extract_audio_segment(y, sr, start_time, end_time):
    # Convert start time from seconds to a sample index
    start_sample = int(start_time * sr)

    # Convert end time from seconds to a sample index
    end_sample = int(end_time * sr)

    # Slice the waveform to keep only the selected segment
    y_segment = y[start_sample:end_sample]

    # Return the extracted audio segment
    return y_segment
