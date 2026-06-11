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

REM --- Python embebido (Opcion C) ----------------------------------------
REM Copia el Python base 3.13 (el que respalda el venv) a scripts\embedded_python.
REM En el 1er arranque, ese Python descarga el backend pesado (torch + motores).
REM Excluimos test/tcl/Tools/Doc (no hacen falta para 'python -m pip'/'-m venv').
REM OJO: NO excluir "Scripts": robocopy /XD casa el nombre en TODO el arbol y
REM tumbaria Lib\venv\scripts\nt\venvlauncher.exe (rompe 'python -m venv').
for /f "delims=" %%i in ('python -c "import sys;print(sys.base_prefix)"') do set "PYBASE=%%i"
echo Preparando Python embebido desde "%PYBASE%" ...
robocopy "%PYBASE%" "scripts\embedded_python" /MIR /XD test tcl Tools Doc __pycache__ idlelib /NFL /NDL /NJH /NJS /NC /NS >nul
REM robocopy devuelve 0-7 en exito; no lo trates como error.
if %ERRORLEVEL% GEQ 8 ( echo ERROR copiando el Python embebido & exit /b 1 )

pyinstaller --noconfirm scripts\transcriptor.spec

echo.
echo Build terminado. Ejecutable en: dist\Transcriptor\Transcriptor.exe
endlocal
