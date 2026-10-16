# =====================================================================================
# Surrogate Language Alignment Program
#
# Bundle the native macOS application with its frontend and audio analysis libraries.
# =====================================================================================

import os
from pathlib import Path
import runpy
import sysconfig

from PyInstaller.utils.hooks import collect_all, copy_metadata

root = Path(SPECPATH)
version = runpy.run_path(str(root / 'surrogate_aligner' / '__init__.py'))['__version__']
identity = os.environ.get('SLAP_CODESIGN_IDENTITY') or None

# Include source and lazy imports needed by librosa and its Numba kernels
librosa_data, librosa_binaries, librosa_imports = collect_all('librosa')

# Retain installed dependency metadata and license files alongside the bundled libraries
metadata = []
for distribution in ('Flask', 'pywebview', 'librosa', 'praat-parselmouth', 'pympi-ling', 'platformdirs'):
    metadata.extend(copy_metadata(distribution, recursive=True))
a = Analysis(
    [str(root / 'desktop.py')],
    pathex=[str(root)],
    binaries=librosa_binaries,
    datas=[
        (str(root / 'frontend' / 'templates'), 'frontend/templates'),
        (str(root / 'frontend' / 'static'), 'frontend/static'),
        (str(root / 'config.toml'), '.'),
        (str(root / 'LICENSE'), '.'),
    ] + librosa_data + metadata,
    hiddenimports=librosa_imports + ['webview.platforms.cocoa'],
    excludes=['PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'webview.platforms.gtk',
              'webview.platforms.qt', 'webview.platforms.winforms'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name='SLAP',
    console=False, strip=False, upx=False,
    codesign_identity=identity,
    entitlements_file=str(root / 'packaging' / 'macos' / 'entitlements.plist'),
)
collection = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='SLAP')
app = BUNDLE(
    collection, name='SLAP.app',
    icon=str(root / 'build' / 'macos' / 'SLAP.icns'),
    bundle_identifier='io.github.gabrielswai.slap',
    version=version,
    info_plist={
        'CFBundleDisplayName': 'SLAP',
        'CFBundleShortVersionString': version.split('-')[0],
        'CFBundleVersion': version.split('-')[0],
        'NSHighResolutionCapable': True,
        'LSMinimumSystemVersion': sysconfig.get_config_var('MACOSX_DEPLOYMENT_TARGET') or '11.0',
    },
)
