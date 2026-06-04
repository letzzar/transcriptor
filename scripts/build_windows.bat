@echo off
REM ==========================================================================
REM  Build de Transcriptor para Windows con Nuitka (standalone).
REM
REM  Uso:  scripts\build_windows.bat
REM  Salida: dist\__main__.dist\Transcriptor.exe  (carpeta standalone)
REM
REM  Activa el venv .venv del repo y compila. Nuitka usa MSVC (cl) si esta
REM  disponible, o descarga MinGW64 (--assume-yes-for-downloads lo acepta).
REM
REM  Nota: el build incluye torch + pyannote + faster-whisper + PySide6 y
REM  ocupa varios GB. La primera compilacion puede tardar bastante.
REM
REM  --include-package-data: data-files de runtime que esas librerias leen
REM    relativos a su __file__ (p.ej. pyannote/audio/telemetry/config.yaml).
REM  --include-distribution-metadata: metadatos .dist-info que pyannote consulta
REM    via importlib.metadata (sin ellos: "No package metadata was found").
REM  Sin estas flags el .exe arranca pero falla al transcribir.
REM ==========================================================================
setlocal
cd /d "%~dp0.."

call ".venv\Scripts\activate.bat"

python -m nuitka ^
  --standalone ^
  --assume-yes-for-downloads ^
  --enable-plugin=pyside6 ^
  --windows-console-mode=disable ^
  --windows-icon-from-ico=src\transcriptor\resources\logo_app.ico ^
  --company-name=letzzar ^
  --product-name=Transcriptor ^
  --file-version=0.2.0 ^
  --product-version=0.2.0 ^
  --include-package=transcriptor ^
  --include-package-data=transcriptor ^
  --include-package-data=pyannote ^
  --include-package-data=faster_whisper ^
  --include-package-data=lightning_fabric ^
  --include-package-data=pytorch_lightning ^
  --include-package-data=asteroid_filterbanks ^
  --include-distribution-metadata=pyannote-audio ^
  --output-dir=dist ^
  --output-filename=Transcriptor.exe ^
  src\transcriptor\__main__.py

echo.
echo Build terminado. Ejecutable en: dist\__main__.dist\Transcriptor.exe
endlocal
