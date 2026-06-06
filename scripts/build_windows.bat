@echo off
REM ==========================================================================
REM  Build de Transcriptor para Windows con PyInstaller (onedir).
REM
REM  Uso:  scripts\build_windows.bat
REM  Salida: dist\Transcriptor\Transcriptor.exe  (+ carpeta _internal\)
REM
REM  IMPORTANTE: ejecutar desde la copia LOCAL (D:\Software mio\Transcriptor),
REM  NUNCA desde el NAS (Y:). PyInstaller no compila a C, asi que la
REM  introspeccion de Lightning/pyannote funciona y la app transcribe.
REM ==========================================================================
setlocal
cd /d "%~dp0.."

call ".venv\Scripts\activate.bat"

pyinstaller --noconfirm scripts\transcriptor.spec

echo.
echo Build terminado. Ejecutable en: dist\Transcriptor\Transcriptor.exe
endlocal
