# =====================================================================================
# Surrogate Language Aligner
#
# Serve the frontend and process upload, note detection, alignment, and download routes.
# =====================================================================================

import atexit
from functools import wraps
from pathlib import Path
import secrets
import sys
from xml.etree import ElementTree

import soundfile as sf
from flask import Flask, jsonify, render_template, request, send_from_directory, session

# Make the project package available when Flask starts from the frontend directory
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from surrogate_aligner import __version__
from surrogate_aligner.aligner import align_sequences, flag_mismatches, make_surrogate_sequence
from surrogate_aligner.annotations import add_alignment, get_elan_segments, load_elan, save_elan
from surrogate_aligner.audio import extract_audio_segment, load_audio
from surrogate_aligner.classification import classify_pitches
from surrogate_aligner.config import OUTPUT_TIERS
from surrogate_aligner.detection import detect_note_onsets, make_note_intervals
from surrogate_aligner.features import extract_pitch, extract_shape
from surrogate_aligner.runs import RunStore
from surrogate_aligner.tones import make_word_sequence, parse_tones as parse_phrase_tones


app = Flask(__name__)

# Reload edited templates and revalidate assets in the local workspace
app.config.update(TEMPLATES_AUTO_RELOAD=True, SEND_FILE_MAX_AGE_DEFAULT=0)

# Keep the displayed development version available to shared templates
app.config["APP_VERSION"] = __version__


# Own uploads per browser session and expire abandoned runs after 24 hours of inactivity
app.secret_key = secrets.token_hex(32)
app.extensions['runs'] = RunStore()
atexit.register(app.extensions['runs'].close)


# Function:     run_required
# Inputs:       view | route requiring an owned upload (callable)
# Outputs:      wrapped | route holding a lease during processing or streaming (callable)
# Description:  Validates upload ownership and prevents cleanup during active requests.

def run_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        run_id = kwargs.get('run_id', request.form.get('run_id', ''))
        if not run_id:
            return jsonify(error="A run ID is required."), 400
        if (not run_id.startswith('surrogate-aligner-') or Path(run_id).name != run_id
                or '/' in run_id or '\\' in run_id):
            return jsonify(error="Invalid run ID."), 400
        if session.get('run_id') != run_id:
            return jsonify(error="The upload was not found or has expired. Upload the files again."), 404
        try:
            lease = app.extensions['runs'].acquire(run_id)
        except KeyError:
            return jsonify(error="The upload was not found or has expired. Upload the files again."), 404
        deferred = False
        try:
            response = app.make_response(view(*args, run_dir=lease.path, **kwargs))
            if response.is_streamed:
                response.direct_passthrough = False
                response.call_on_close(lease.close)
                deferred = True
            return response
        finally:
            if not deferred:
                lease.close()
    return wrapped


# Function:     delete_run
# Inputs:       run_id | upload to abandon (str)
# Outputs:      response | cleanup confirmation (Response)
# Description:  Removes this browser session's abandoned upload after active requests finish.

@app.post('/runs/<run_id>/delete')
@run_required
def delete_run(run_id, run_dir):
    app.extensions['runs'].discard(run_id)
    return jsonify(deleted=True)


# Function:     index
# Inputs:       None
# Outputs:      page | rendered frontend page (str)
# Description:  Displays the upload form and results section.

@app.get("/")
def index():
    # Version assets so the browser loads styles and scripts matching this template
    asset_versions = {
        name: (Path(app.static_folder) / name).stat().st_mtime_ns
        for name in ("style.css", "script.js")
    }
    response = app.make_response(render_template("index.html", asset_versions=asset_versions))
    response.headers["Cache-Control"] = "no-store"
    return response


# Function:     upload_files
# Inputs:       None
# Outputs:      response | run ID, annotation tiers, and HTTP status (tuple)
# Description:  Saves the audio and ELAN files and returns the available annotation tiers.

@app.post("/upload")
def upload_files():
    # Read the audio recording and ELAN annotations from the submitted form
    audio_file = request.files.get("audio")
    elan_file = request.files.get("elan")

    # Require both files and check their filename extensions
    for uploaded_file, extension in ((audio_file, ".wav"), (elan_file, ".eaf")):
        if uploaded_file is None or not uploaded_file.filename:
            return jsonify(error=f"A {extension} file is required."), 400
        if not uploaded_file.filename.lower().endswith(extension):
            return jsonify(error=f"Expected a {extension} file."), 400

    # Check that the recording is a readable WAV file containing audio frames
    try:
        with sf.SoundFile(audio_file.stream) as audio:
            if audio.format not in {"WAV", "WAVEX", "RF64"} or audio.frames == 0:
                return jsonify(error="The WAV file must contain audio."), 400
    except (sf.LibsndfileError, ValueError, OSError):
        return jsonify(error="The WAV file is invalid or unreadable."), 400
    finally:
        # Rewind the audio stream so the complete file can be saved later
        audio_file.stream.seek(0)

    # Parse the EAF XML and check for the ELAN annotation document root
    try:
        annotations = ElementTree.parse(elan_file.stream)
        if annotations.getroot().tag != "ANNOTATION_DOCUMENT":
            return jsonify(error="The EAF file must be an ELAN annotation document."), 400
    except (ElementTree.ParseError, ValueError, OSError):
        return jsonify(error="The EAF file is invalid or unreadable."), 400
    finally:
        # Rewind the annotation stream so the complete file can be saved later
        elan_file.stream.seek(0)

    # Create a unique temporary folder for this upload run
    run_dir = app.extensions['runs'].create()
    try:
        # Save both files with consistent names for later processing
        audio_file.save(run_dir / "audio.wav")
        elan_file.save(run_dir / "annotations.eaf")
    except Exception:
        # Remove any partially saved files if the upload cannot be completed
        app.extensions['runs'].discard(run_dir.name)
        raise

    # Read tier names from the uploaded ELAN document in their original order
    tiers = [tier.get("TIER_ID") for tier in annotations.getroot().findall("TIER")
             if tier.get("TIER_ID")]

    # Replace only the previous upload owned by this browser session
    previous_run = session.get('run_id')
    session['run_id'] = run_dir.name
    if previous_run:
        app.extensions['runs'].discard(previous_run)

    # Return the unique folder name and tier choices for the frontend
    return jsonify(run_id=run_dir.name, tiers=tiers), 200


# Function:     parse_tones
# Inputs:       None
# Outputs:      response | parsed annotation segments and HTTP status (tuple)
# Description:  Parses word-level tones from the selected ELAN annotation tier.

@app.post("/parse-tones")
@run_required
def parse_tones(run_dir):
    # Read the upload run and selected annotation tier from the submitted form
    run_id = request.form.get("run_id", "")
    input_tier = request.form.get("input_tier", "")
    default_tone = request.form.get("default_tone", "L")
    if not run_id or not input_tier:
        return jsonify(error="A run ID and annotation tier are required."), 400

    # Require a supported default tone for unmarked vowels
    if default_tone not in ("L", "M"):
        return jsonify(error="The default tone must be L or M."), 400

    elan_path = run_dir / "annotations.eaf"
    if not elan_path.is_file():
        return jsonify(error="The uploaded ELAN file was not found."), 404

    # Load the uploaded annotations and require an existing tier
    try:
        eaf = load_elan(elan_path)
        if input_tier not in eaf.get_tier_names():
            return jsonify(error="The selected annotation tier was not found."), 400
        segments = get_elan_segments(eaf, input_tier)
    except (ElementTree.ParseError, ValueError, OSError, KeyError):
        return jsonify(error="The selected ELAN annotations could not be read."), 400

    # Parse each phrase and retain its interval and word-level tone information
    for segment in segments:
        phrase = segment["label"]
        try:
            segment["tones"] = parse_phrase_tones(phrase, default_tone=default_tone)
            segment["word_sequence"] = make_word_sequence(phrase.split(), segment["tones"])
        except ValueError as error:
            return jsonify(error=f"Phrase at {segment['start']:.3f}s: {error}"), 400

    # Return the parsed segments for the selected upload and tier
    return jsonify(run_id=run_id, input_tier=input_tier,
                   default_tone=default_tone, segments=segments), 200


# Function:     detect_notes
# Inputs:       None
# Outputs:      response | annotation segments with note intervals and HTTP status (tuple)
# Description:  Detects notes, aligns tones, and exports the selected annotation tier.

@app.post("/detect-notes")
@run_required
def detect_notes(run_dir):
    # Read the upload run and selected annotation tier from the submitted form
    run_id = request.form.get("run_id", "")
    input_tier = request.form.get("input_tier", "")
    default_tone = request.form.get("default_tone", "L")
    if not run_id or not input_tier:
        return jsonify(error="A run ID and annotation tier are required."), 400

    # Require the same default tone choices as the tone parsing route
    if default_tone not in ("L", "M"):
        return jsonify(error="The default tone must be L or M."), 400

    # Keep generated tiers from replacing the selected source annotations
    if input_tier in OUTPUT_TIERS.values():
        return jsonify(error="Select a source tier rather than a generated alignment tier."), 400

    audio_path = run_dir / "audio.wav"
    elan_path = run_dir / "annotations.eaf"
    if not audio_path.is_file() or not elan_path.is_file():
        return jsonify(error="The uploaded audio or ELAN file was not found."), 404

    # Load the recording once and read the selected annotation intervals
    try:
        eaf = load_elan(elan_path)
        if input_tier not in eaf.get_tier_names():
            return jsonify(error="The selected annotation tier was not found."), 400
        segments = get_elan_segments(eaf, input_tier)
        if not segments:
            return jsonify(error="The selected tier has no annotations."), 400
        y, sr, duration = load_audio(audio_path)
    except (ElementTree.ParseError, sf.LibsndfileError, ValueError, OSError, KeyError):
        return jsonify(error="The uploaded audio or ELAN annotations could not be read."), 400

    # Extract the audio for each annotated segment using times in seconds
    audio_segments = []
    for segment in segments:
        start_time = segment["start"]
        end_time = segment["end"]
        if not 0 <= start_time < end_time <= duration:
            return jsonify(error="An annotation interval is outside the recording."), 400
        y_segment = extract_audio_segment(y, sr, start_time, end_time)
        if len(y_segment) == 0:
            return jsonify(error="An annotation interval contains no audio samples."), 400
        audio_segments.append(y_segment)

    # Detect note intervals and align each phrase using the existing acoustic workflow
    full_alignment = []
    skipped_segments = []
    processed_count = 0
    try:
        for index, (segment, y_segment) in enumerate(zip(segments, audio_segments)):
            # Validate transcription before acoustic analysis or exporting any phrase
            try:
                tones = parse_phrase_tones(segment["label"], default_tone=default_tone)
                word_sequence = make_word_sequence(segment["label"].split(), tones)
            except ValueError as error:
                return jsonify(error=f"Phrase at {segment['start']:.3f}s: {error}"), 400
            if not word_sequence:
                skipped_segments.append(dict(segment, reason="No words with tone patterns."))
                continue
            onset_times = detect_note_onsets(y_segment, sr)
            segment["note_intervals"] = make_note_intervals(
                onset_times, segment["start"], segment["end"])
            intervals = segment["note_intervals"]
            if not intervals:
                skipped_segments.append(dict(segment, reason="No note onsets detected."))
                continue

            # Classify notes and parse the phrase with the selected default tone
            pitches = extract_pitch(y_segment, sr, intervals, segment["start"])
            shapes = extract_shape(y_segment, sr, intervals, segment["start"])
            surrogate_sequence = make_surrogate_sequence(
                intervals, classify_pitches(pitches, shapes))
            alignment = flag_mismatches(align_sequences(word_sequence, surrogate_sequence))

            # Preserve phrase boundaries when grouping the output annotations
            for item in alignment:
                item.update(segment_index=index, segment_start=segment["start"],
                            segment_end=segment["end"], phrase=segment["label"])
            full_alignment.extend(alignment)
            processed_count += 1
    except (ValueError, RuntimeError):
        return jsonify(error="Notes could not be analyzed in the selected audio."), 400

    # Report incomplete processing even when other phrases produced a usable export
    summary = dict(total_count=len(segments), processed_count=processed_count,
                   skipped_count=len(skipped_segments), skipped_segments=skipped_segments)
    if not full_alignment:
        return jsonify(error="No phrases could be aligned. See the skipped phrase details.", **summary), 400

    # Save the completed alignment before enabling the frontend download
    try:
        add_alignment(eaf, full_alignment, OUTPUT_TIERS)
        save_elan(eaf, run_dir / "output.eaf")
    except (ValueError, OSError, KeyError):
        return jsonify(error="The aligned ELAN file could not be saved."), 500

    # Return each annotation and its detected note intervals in seconds
    return jsonify(run_id=run_id, input_tier=input_tier, default_tone=default_tone,
                   segments=segments, output_ready=True, **summary), 200


# Function:     download_output
# Inputs:       run_id | identifier for a completed alignment run (str)
# Outputs:      response | EAF attachment or error response
# Description:  Downloads the updated ELAN annotation file.

@app.get("/download/<run_id>")
@run_required
def download_output(run_id, run_dir):
    # Require a completed output file for the requested run
    output_path = run_dir / "output.eaf"
    if not output_path.is_file():
        return jsonify(error="The output ELAN file was not found."), 404

    # Remove the run files after the download response has finished streaming
    response = send_from_directory(run_dir, "output.eaf", as_attachment=True,
                                   conditional=False, max_age=0)
    response.headers["Cache-Control"] = "no-store"
    response.direct_passthrough = False
    response.call_on_close(lambda: app.extensions['runs'].discard(run_id))
    return response


if __name__ == "__main__":
    # Start the local frontend server
    app.run(host="127.0.0.1", port=5000)
