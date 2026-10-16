# =====================================================================================
# Surrogate Language Alignment Program
#
# Build a macOS app and drag-to-install disk image from the active Python environment.
# =====================================================================================

import argparse
import os
from pathlib import Path
import platform
import runpy
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / 'build' / 'macos'
DIST = ROOT / 'dist'


# Function:     create_icon
# Inputs:       None
# Outputs:      None
# Description:  Draws the existing asymmetric waveform as a macOS application icon.

def create_icon():
    from PIL import Image, ImageDraw

    icon = Image.new('RGBA', (1024, 1024))
    draw = ImageDraw.Draw(icon)
    draw.rounded_rectangle((32, 32, 992, 992), radius=210, fill='#285b48')
    for x, top, bottom in ((224, 424, 600), (296, 336, 688), (368, 248, 776),
                           (440, 380, 644), (512, 314, 710), (584, 204, 820),
                           (656, 292, 732), (728, 402, 622), (800, 446, 578)):
        draw.rounded_rectangle((x - 20, top, x + 20, bottom), radius=20, fill='#f5f7f2')
    icon.save(BUILD / 'SLAP.icns', format='ICNS')


# Function:     main
# Inputs:       None
# Outputs:      None
# Description:  Builds, checks, and packages the app, optionally notarizing a signed release.

def main():
    parser = argparse.ArgumentParser(description='Build SLAP for the current Mac architecture.')
    parser.add_argument('--notarize-profile', help='Existing notarytool keychain profile for a signed release')
    args = parser.parse_args()
    if sys.platform != 'darwin':
        parser.error('This build must run on macOS.')
    if args.notarize_profile and not os.environ.get('SLAP_CODESIGN_IDENTITY'):
        parser.error('Set SLAP_CODESIGN_IDENTITY to a Developer ID Application identity before notarizing.')

    BUILD.mkdir(parents=True, exist_ok=True)
    DIST.mkdir(exist_ok=True)
    create_icon()
    version = runpy.run_path(str(ROOT / 'surrogate_aligner' / '__init__.py'))['__version__']
    environment = os.environ.copy()
    environment['PYINSTALLER_CONFIG_DIR'] = str(BUILD / 'cache')
    subprocess.run([
        sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
        '--distpath', str(DIST), '--workpath', str(BUILD / 'work'), str(ROOT / 'SLAP.spec'),
    ], cwd=ROOT, env=environment, check=True)

    # Exercise the frozen dependencies without opening a GUI or using the source tree
    report = BUILD / 'smoke-test.json'
    check_environment = os.environ.copy()
    for variable in ('PYTHONHOME', 'PYTHONPATH', 'VIRTUAL_ENV'):
        check_environment.pop(variable, None)
    check_environment['PATH'] = '/usr/bin:/bin:/usr/sbin:/sbin'
    subprocess.run([str(DIST / 'SLAP.app' / 'Contents' / 'MacOS' / 'SLAP'),
                    '--smoke-test', str(report)], cwd=tempfile.gettempdir(),
                   env=check_environment, check=True)
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(DIST / 'SLAP.app')], check=True)

    # Keep the staging folder limited to the application and an Applications shortcut
    with tempfile.TemporaryDirectory(prefix='dmg-', dir=BUILD) as temporary:
        stage = Path(temporary)
        shutil.copytree(DIST / 'SLAP.app', stage / 'SLAP.app', symlinks=True)
        (stage / 'Applications').symlink_to('/Applications')
        (stage / 'Install.txt').write_text(
            'Drag SLAP into Applications, then open SLAP from Applications.\n'
            'No Python or Terminal is required.\n'
            'If macOS blocks an unsigned development build, request a signed release from the developer.\n'
        )
        image = DIST / f'SLAP-{version}-macos-{platform.machine()}.dmg'
        subprocess.run(['hdiutil', 'create', '-volname', 'SLAP', '-srcfolder', str(stage),
                        '-format', 'UDZO', '-ov', str(image)], check=True)

    if args.notarize_profile:
        subprocess.run(['xcrun', 'notarytool', 'submit', str(image), '--keychain-profile',
                        args.notarize_profile, '--wait'], check=True)
        subprocess.run(['xcrun', 'stapler', 'staple', str(image)], check=True)
        subprocess.run(['xcrun', 'stapler', 'validate', str(image)], check=True)
    print(f'Application: {DIST / "SLAP.app"}\nInstaller: {image}\nVerification: {report}')
    if not os.environ.get('SLAP_CODESIGN_IDENTITY'):
        print('Development build: ad-hoc signed, not Developer ID signed or notarized.')


if __name__ == '__main__':
    main()
