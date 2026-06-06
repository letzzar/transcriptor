# -*- mode: python ; coding: utf-8 -*-
# Spec de PyInstaller para Transcriptor (Windows, onedir).
#
# Build:  pyinstaller --noconfirm scripts/transcriptor.spec   (DESDE la raiz del repo)
# Salida: dist/Transcriptor/Transcriptor.exe  (+ carpeta _internal/)
#
# IMPORTANTE: compilar SIEMPRE en disco local (la copia D:), NUNCA en el NAS (Y:).
# PyInstaller no compila a C (a diferencia de Nuitka), asi que la introspeccion
# de Lightning/pyannote (save_hyperparameters) funciona y la app transcribe.

import os

from PyInstaller.utils.hooks import collect_all, copy_metadata

# SPECPATH = carpeta del spec (scripts/). La raiz del repo es su padre. Asi el
# build funciona se ejecute desde donde se ejecute.
ROOT = os.path.dirname(SPECPATH)

datas = [(os.path.join(ROOT, 'src/transcriptor/resources'), 'transcriptor/resources')]
binaries = []
hiddenimports = []

# Metadatos .dist-info que estas librerias consultan via importlib.metadata.
for dist in ('pyannote.audio', 'transformers'):
    datas += copy_metadata(dist)

# Paquetes con submodulos/datos cargados dinamicamente (clases de modelo, etc.).
for pkg in ('pyannote.audio', 'faster_whisper', 'lightning', 'torchmetrics',
            'asteroid_filterbanks', 'transformers'):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(pkg)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    [os.path.join(ROOT, 'src/transcriptor/__main__.py')],
    pathex=[os.path.join(ROOT, 'src')],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    icon=[os.path.join(ROOT, 'src/transcriptor/resources/logo_app.ico')],
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
