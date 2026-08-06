# -*- mode: python ; coding: utf-8 -*-
# Spec de PyInstaller para Transcriptor (Windows, onedir) — bundle THIN.
#
# Build:  pyinstaller --noconfirm scripts/transcriptor.spec   (DESDE la raiz del repo)
# Salida: dist/Transcriptor/Transcriptor.exe  (+ carpeta _internal/)
#
# IMPORTANTE: compilar SIEMPRE en disco local (la copia D:), NUNCA en el NAS (Y:).
# PyInstaller no compila a C (a diferencia de Nuitka), asi que la introspeccion
# de Lightning/pyannote (save_hyperparameters) funciona y la app transcribe.
#
# OPCION C (embed): el stack pesado (torch + motores, ~2 GB) NO se empaqueta. Se
# descarga en el primer arranque (runtime/provision.py) con el Python embebido y
# se carga desde la carpeta del usuario. Aqui solo va la UI + codigo + el Python
# embebido que prepara build_windows.bat en scripts/embedded_python.

import os
import sys

from PyInstaller.utils.hooks import collect_all

# SPECPATH = carpeta del spec (scripts/). La raiz del repo es su padre. Asi el
# build funciona se ejecute desde donde se ejecute.
ROOT = os.path.dirname(SPECPATH)

datas = [
    (os.path.join(ROOT, 'src/transcriptor/resources'), 'transcriptor/resources'),
    # Python embebido (cp313) para provisionar el backend en el 1er arranque.
    # OJO: el destino NO puede llamarse 'python': en macOS PyInstaller crea el
    # symlink 'Python' (libpython del bundle) en _internal/ y APFS es
    # case-insensitive → colisión (NotADirectoryError en COLLECT).
    (os.path.join(ROOT, 'scripts/embedded_python'), 'python_embed'),
]
binaries = []
hiddenimports = []

# keyring carga sus backends DINAMICAMENTE (entry points), asi que el analisis
# estatico de PyInstaller no ve keyring.backends.Windows ni su dependencia
# win32ctypes. Sin ellos, keyring cae al backend "fail" y get_hf_token() lanza
# NoKeyringError. Los recolectamos explicitamente (antes se colaban como
# transitivos del stack pesado, que ahora ya no se empaqueta).
# win32ctypes solo existe (y hace falta) en Windows.
_keyring_pkgs = ('keyring', 'win32ctypes') if sys.platform == 'win32' else ('keyring',)
for pkg in _keyring_pkgs:
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

# El stack pesado se descarga aparte (Opcion C): lo excluimos para que
# PyInstaller no lo arrastre por los imports perezosos de engines/ y pipeline/.
# En runtime se importa desde el backend del usuario (sys.path lo anade
# runtime.provision.activate()).
excludes = [
    'torch', 'torchaudio', 'torchvision',
    'faster_whisper', 'ctranslate2',
    'pyannote', 'pyannote.audio', 'pyannote.core', 'pyannote.database',
    'pyannote.metrics', 'pyannote.pipeline',
    'transformers', 'tokenizers',
    'lightning', 'pytorch_lightning', 'lightning_fabric',
    'torchmetrics', 'asteroid_filterbanks', 'speechbrain',
]

a = Analysis(
    [os.path.join(ROOT, 'src/transcriptor/__main__.py')],
    pathex=[os.path.join(ROOT, 'src')],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Transcriptor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # El .ico es formato Windows; en macOS el icono va en el BUNDLE (.icns).
    icon=[os.path.join(ROOT, 'src/transcriptor/resources/logo_app.ico')]
    if sys.platform == 'win32' else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Transcriptor',
)

# macOS: envolver el onedir en un .app (PyInstaller lo firma ad-hoc en arm64).
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='Transcriptor.app',
        icon=os.path.join(ROOT, 'src/transcriptor/resources/logo_app.icns'),
        bundle_identifier='com.letzzar.transcriptor',
        info_plist={
            'CFBundleShortVersionString': '0.9.0',
            'NSHighResolutionCapable': True,
        },
    )
