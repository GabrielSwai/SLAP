# 🎵 SLAP (Surrogate Language Alignment Program)

SLAP is a semi-automatic research tool for aligning spoken tone patterns with musical surrogate recordings and exporting word-level annotations to ELAN. Development initially centered on the Kinande language (Bantu, DRC); support for configurable languages and instruments is planned.

Researchers supply a recording and an existing ELAN file whose annotations identify the corresponding phrases and recording intervals. SLAP detects notes within those intervals, classifies their acoustic features, and aligns the resulting surrogate tones with the tone patterns parsed from the annotation text.

This project began as my [Dartmouth COSC 72](https://dartmouth.smartcatalogiq.com/en/current/orc/departments-programs-undergraduate/computer-science/cosc-computer-science-undergraduate/cosc-72) final project.

## Current version: v0.1.0-dev

The current development version includes a standalone macOS desktop application, a local Flask frontend, and a command-line pipeline. **Home is the only implemented page.** Review, Calibration, Settings, and Help appear in the navbar as disabled placeholders.

### Home workflow

1. **Upload:** provide a `.wav` recording and an ELAN `.eaf` annotation file. The program validates the files and loads the available tier names.
2. **Tone parsing:** select the source annotation tier and choose low (`L`) or mid (`M`) as the default for unmarked vowels. Each phrase is split into words and parsed into word-level tone patterns.
3. **Alignment:** detect note onsets and intervals within the annotated phrases and align the spoken and surrogate tone sequences.
4. **Download:** export an updated `.eaf` file containing word, spoken-tone, and surrogate-tone tiers.

The interface displays processing status, errors, and processed/skipped phrase counts with intervals and reasons for any skipped phrases. It does not yet display the alignment, acoustic plots, mismatch diagnostics, or confidence scores for interactive review.

### Current analysis behavior

- Phrase text and timing come from the selected ELAN tier; users do not enter start and end times separately in the frontend.
- Tone parsing normalizes Unicode accents and recognizes a broad set of Latin and IPA vowels. It supports level tones, extra-high/extra-low labels, and several rising and falling contours. The unmarked-vowel default is selectable as `L` or `M`. Standalone punctuation does not consume notes. Unsupported vowel markings or words without recognizable vowels are rejected with the phrase location so the transcription can be checked.
- The vowel inventory and tone-mark mappings remain embedded in `surrogate_aligner/tones.py`; they are not loaded from a specific language profile.
- Surrogate classification remains binary **H/L**, even when the spoken transcription contains other tone labels.
- As a temporary export policy, surrogate H/L labels are written as **X** in ELAN (for example, `H-L` becomes `X-X`), as pitch detection is currently hard-coded for a specific type of drum in Kinande. Spoken tones, timing, and internal alignment are preserved. To restore classified export labels, pass `ambiguous_surrogate_tones=False` to `add_alignment`, or change its default when reliable classification is available. This policy applies to both the frontend and command-line exports.
- `classify_pitches` uses a fixed **120 Hz** pitch boundary and a **0.4** normalized shape threshold when individual pitch estimates are unavailable. When no valid pitches are available for a segment, it classifies using the median normalized shape score. Shape features include RMS-based decay measurements.
- The alignment code flags matches, mismatches, and gaps internally. The command-line pipeline also reports an overall confidence score based on the proportion of exact tone matches; this is not a calibrated probability or an interactive review feature.

### Inputs and outputs

Inputs are a WAV recording, its EAF annotation file, and a source tier containing phrase labels with valid intervals inside the recording. Speech transcription and phrase-to-recording correspondence must already be established manually.

For example, with the default tone set to `L`:

```text
Asá   → L-H
hano! → L-L
```

Output tier names are configured in `config.toml`:

| Content | Default tier |
| --- | --- |
| Aligned words | `Surrogate_Words-txt-gbe` |
| Spoken tone patterns | `Surrogate_Words-tones` |
| Surrogate tone patterns | `Surrogate_Words-music` |

Existing annotations on these output tiers are cleared and replaced in the exported copy. The frontend prevents selecting one of these generated tiers as the source tier.

Uploaded files and generated output are stored temporarily on the local server. In desktop mode, the native Save dialog lets you choose an export location; cancelling or failing to save retains the result for retry. The run directory is removed after a successful save. In browser mode, it is removed when the download response closes. Replacing the selected files or uploading another pair discards the previous upload. Active processing and downloads are protected from expiry; idle uploads expire after 24 hours. Closing the desktop application, or normally stopping the browser server, removes uploads owned by that process. Forced termination may leave files for the operating system to clear from temporary storage. Upload the files again to run another analysis after saving. Persistent projects and run history are not yet implemented.

## Installing on macOS

Researchers do not need Python or a terminal to use the packaged application:

1. Open `SLAP-0.1.0-dev-macos-arm64.dmg` from your distribution, or from `dist/` after a local build.
2. Drag **SLAP** into **Applications**.
3. Open **SLAP** from Applications.
4. Upload a WAV recording and EAF annotations, parse tones, align, and save the exported EAF file.

The current build supports **Apple Silicon Macs running macOS 15 or later**. It is not an Intel or universal build. Python and the analysis dependencies are bundled inside the app. Closing the window stops the local server, and the GitHub link opens in your default browser.

The current development build is **ad-hoc signed, not Developer ID signed or notarized**. macOS may block downloaded copies. Public distribution requires a Developer ID-signed and notarized release; that release workflow is supported by the build script but requires the developer's Apple signing credentials.

Diagnostic logs are stored in `~/Library/Logs/SLAP/desktop.log`. Runtime caches and temporary analysis files are stored outside the application bundle.

## Running SLAP from source

Run commands from the project root. Use **Python 3.13** for the tested source and build environment. The pinned dependency set requires Python 3.13 or newer (`audioop-lts` requires 3.13+); Python 3.11/3.12 will not install the requirements unchanged.

### Environment setup

macOS/Linux:

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Windows Command Prompt:

```bat
py -3.13 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### Launch options

After activating the environment, choose one of these entry points:

| Mode | Command | Usage |
| --- | --- | --- |
| Desktop | `python desktop.py` | Native window, file chooser, and Save dialog; first install `python -m pip install -r requirements-desktop.txt` |
| Browser | `python frontend/app.py` | Open `http://127.0.0.1:5000` |
| Command line | `python main.py` | Configure input files, source tier, output paths, and output tiers in `config.toml` |

For the command-line pipeline, `INPUT` is the shared filename stem of the WAV and EAF files in `DATA_DIR`. The pipeline saves the output and prints its aligned-item count and overall confidence score. It uses the tone parser's default `L` setting. `LANGUAGE_PROFILE` is not yet connected to the pipeline.

### Building the macOS application

On macOS, with the environment activated:

```bash
python -m pip install -r requirements-build-macos.txt
python scripts/build_macos.py
```

The build creates:

- `dist/SLAP.app`: the standalone application.
- `dist/SLAP-<version>-macos-<architecture>.dmg`: the drag-to-install disk image.
- `build/macos/smoke-test.json`: results from the bundled analysis and export check.

The build checks the frozen app outside the source environment and verifies its code signature. The save-dialog selection is simulated during the automated check; native window and dialog behavior still require manual testing before release.

The version is defined in `surrogate_aligner/__init__.py` and shared by the frontend and build. For signing, notarization, platform compatibility, and release verification, see [macOS release instructions](packaging/macos/README.md). Generated apps, disk images, and build caches are excluded from Git; distribute installers as release assets rather than committing them.

### Development checks

```bash
python -m unittest discover -v
node frontend/test_script.js
```

Standard discovery includes the frontend tests. These checks cover desktop lifecycle and overwrite protection, startup alerts, run expiry and cleanup, tone parsing, partial exports, ambiguous tone export, frontend routes, and browser/desktop download states. Node.js is needed only for the JavaScript checks, not to run SLAP.

## Planned pages

| Page | Scope | Status |
| --- | --- | --- |
| **Home** | Upload, tone parsing, alignment, and download | Implemented |
| **Calibration** | Extract sample phrases, manually tune analysis parameters, and run the v1 alignment workflow | Planned |
| **Review** | Highlight mismatches, ambiguities, and other cases requiring inspection; expose waveform and pitch information, audio playback, and confidence scores | Planned |
| **Settings** | Select the language and instrument used for analysis | Planned; depends on profile support |
| **Help** | Documentation covering inputs, workflow, parameters, methods, and interpretation | Planned |

The Calibration, Review, Settings, and Help items are disabled placeholders, not working pages. Language, instrument, and calibration directories exist as scaffolding; their presence does not indicate implemented functionality.

## v1 roadmap

### Language parameters loaded from files

Move language-specific assumptions into profile files and connect them to the frontend and pipeline:

- **`tones.py` / `parse_tones`:** parameterize vowel inventories, tone inventories, diacritic mappings, and unmarked-vowel defaults. The parser has already expanded beyond the original five-vowel, default-L, H/L/HL-only design, but these rules are still hard-coded.
- **`classification.py` / `classify_pitches`:** replace the assumption that every surrogate tone belongs to a binary H/L system with language-appropriate classification settings.

### Frontend development

The Home frontend is already implemented. Continue building the planned Calibration, Review, Settings, and Help pages, connecting each to working analysis functionality rather than placeholder navigation.

### Adjustable manual calibration

Expose the currently fixed analysis settings for researcher-controlled tuning:

- Extract representative sample phrases for calibration.
- Adjust the `classify_pitches` pitch boundary, currently `120.0` Hz.
- Adjust the normalized shape threshold, currently `0.4`, and the use of RMS-derived decay features as a fallback when pitch estimates are unavailable.
- Apply the selected parameters to the v1 alignment workflow.

## Beyond v1

- **Instrument parameterization:** instrument profiles for acoustic features and analysis settings.
- **Basic calibration:** additional calibration support beyond the v1 manual-tuning workflow; its scope remains to be defined.
- **Ambiguity handling:** represent uncertain classifications and alignments for review instead of relying only on a single hard decision.
- **Updated alignment algorithm:** improve handling of tone patterns, gaps, and correspondence between spoken and surrogate sequences.

These are planned directions, not features available in the current release. In particular, instrument selection on Settings depends on the later instrument-parameterization work, and ambiguity-aware Review features depend on later analysis changes.

## Scope and limitations

SLAP currently does not automatically separate speech from instrumental passages, transcribe speech, determine which phrase corresponds to which passage, or perform speech recognition or forced alignment. Those decisions are supplied through the ELAN annotations.

The current thresholds and binary classifier are an MVP, not a language- or instrument-independent model. Exported alignments require researcher inspection; interactive correction and diagnostic visualization are planned for Review.

## Project structure

```text
SLAP/
├── frontend/
│   ├── app.py                  # Flask routes
│   ├── static/                 # Styles and browser-side workflow
│   ├── templates/
│   │   ├── index.html          # Home workflow
│   │   └── partials/           # Shared navbar and footer
│   └── test_app.py             # Frontend route checks
├── surrogate_aligner/
│   ├── __init__.py             # Shared application version
│   ├── desktop_check.py        # Frozen application smoke check
│   ├── runs.py                 # Owned upload lifecycle and inactivity expiry
│   ├── annotations.py          # ELAN reading and export
│   ├── audio.py                # Recording loading and segment extraction
│   ├── detection.py            # Note onset detection
│   ├── features.py             # Pitch and decay features
│   ├── classification.py       # H/L classification
│   ├── tones.py                # Spoken tone parsing
│   ├── aligner.py              # Sequence alignment and diagnostics
│   ├── pipeline.py             # Command-line analysis workflow
│   ├── calibration/            # Planned calibration scaffolding
│   ├── languages/              # Planned language profile scaffolding
│   └── instruments/            # Planned instrument scaffolding
├── data/                       # Input recordings and annotations
├── outputs/                    # Includes the intentional aligned_output.eaf example
├── config.toml                 # Pipeline settings and output tiers
├── main.py                     # Command-line entry point
├── desktop.py                  # Native window, server lifecycle, and saving
├── SLAP.spec                   # PyInstaller macOS bundle specification
├── scripts/build_macos.py      # App and DMG build command
├── packaging/macos/            # Entitlements and release instructions
├── requirements.txt            # Core dependencies
├── requirements-desktop.txt    # Optional desktop dependencies
├── requirements-build-macos.txt
├── test_desktop.py             # Desktop regression checks
├── test_annotations.py         # ELAN export regression checks
├── test_pipeline.py            # CLI partial-export and failure checks
├── test_runs.py                # Upload lifecycle and expiry checks
└── test_tones.py               # Transcription validation checks
```
