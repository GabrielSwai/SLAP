# macOS releases

SLAP is distributed as `SLAP.app` inside a drag-to-install DMG. Researchers open the DMG, drag SLAP to Applications, and open SLAP. Python, pip, and a terminal are not needed on their computers.

## Build

Run on macOS from the project root, using a Python 3.13 virtual environment:

```bash
python -m pip install -r requirements-build-macos.txt
python scripts/build_macos.py
```

The build produces:

- `dist/SLAP.app`: the standalone, windowed application.
- `dist/SLAP-<version>-macos-<architecture>.dmg`: the installer image containing SLAP, an Applications shortcut, and installation instructions.
- `build/macos/smoke-test.json`: results of the frozen end-to-end verification.

The build includes the Python interpreter, native dependencies, templates, static files, default configuration, and dependency metadata/licenses. Personal input recordings are not included. The app uses temporary files and user log/cache directories rather than writing inside its signed bundle. Uploads expire after 24 hours of inactivity and are removed on normal desktop shutdown. Active requests hold their uploads until processing or streaming finishes. Startup failures use the system macOS alert rather than requiring Tcl/Tk. Saving confirms replacement against the final EAF filename. The waveform app icon is generated during the build.

Version information comes from `surrogate_aligner/__init__.py` and is shared by the app footer and build metadata. Development suffixes are retained in the DMG filename; macOS bundle version fields use the numeric portion.

The build targets the architecture of the active Python interpreter. The initial build is **Apple Silicon (`arm64`), macOS 15 or newer**, matching this machine's Python runtime. This is not an Intel or universal build. To support older macOS versions or Intel hardware, rebuild and test with an appropriate Python and dependency environment; changing the bundle's minimum-version field alone does not make its native libraries compatible.

## Verification

The build automatically runs the bundled executable outside the repository, with Python environment overrides removed and only system tools on PATH. It generates a WAV and EAF pair, exercises upload and tone parsing, runs the real onset/pitch/shape/alignment code, saves through the desktop save implementation, reads back the output, and checks cleanup and server shutdown. It also checks the bundle's code signature.

The automated check simulates the Save dialog's selected path; it does not visually test the native dialogs or window. Before a public release, manually test the copied application on a clean Mac without Python: opening files, cancelling and completing a save, opening the GitHub link, and closing/reopening the window.

To rerun the frozen check during development:

```bash
dist/SLAP.app/Contents/MacOS/SLAP --smoke-test /tmp/slap-check.json
```

## Signing and notarization

Without credentials, PyInstaller creates an ad-hoc-signed development application. This verifies bundle integrity locally but is not a Developer ID signature or Apple notarization. Downloaded development builds may be blocked by Gatekeeper; do not describe them as a frictionless public release.

For a public release, configure an available **Developer ID Application** identity and an existing `notarytool` keychain profile, then build:

```bash
export SLAP_CODESIGN_IDENTITY='Developer ID Application: Your Name (TEAMID)'
python scripts/build_macos.py --notarize-profile SLAP-notary
```

The script signs bundled code using the supplied identity, submits the DMG to Apple, waits for the result, and staples and validates the notarization ticket. Credentials are read from the existing keychain profile, not stored in the repository. The included entitlements permit LLVM/Numba JIT compilation in a hardened-runtime build.

The build does not publish or upload a release to GitHub. Upload the tested DMG to the desired release separately.
