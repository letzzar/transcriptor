@echo off
REM ==========================================================================
REM  Build de Transcriptor para Windows con Nuitka (standalone).
REM
REM  Uso:  scripts\build_windows.bat
REM  Salida: dist\Transcriptor.dist\Transcriptor.exe  (carpeta standalone)
REM
REM  Activa el venv .venv del repo y compila. Nuitka usa MSVC (cl) si esta
REM  disponible, o descarga MinGW64 (--assume-yes-for-downloads lo acepta).
REM
REM  Nota: el build incluye torch + pyannote + faster-whisper + PySide6 y
REM  ocupa varios GB. La primera compilacion puede tardar bastante.
REM ==========================================================================
setlocal
cd /d "%~dp0.."

call ".venv\Scripts\activate.bat"

REM  Flags validadas: con estas el .exe compila y arranca. Nuitka auto-incluye
REM  los data-files de torch/sklearn/tzdata via sus plugins. Si al TRANSCRIBIR
REM  en el .exe falta algun data-file de runtime (pyannote/lightning), anade:
REM    --include-package-data=pyannote ^
REM    --include-package-data=faster_whisper ^
REM    --include-package-data=lightning_fabric ^
REM    --include-package-data=pytorch_lightning ^
REM    --include-package-data=asteroid_filterbanks ^
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
  --output-dir=dist ^
  --output-filename=Transcriptor.exe ^
  src\transcriptor\__main__.py

echo.
echo Build terminado. Ejecutable en: dist\__main__.dist\Transcriptor.exe
endlocal
