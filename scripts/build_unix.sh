#!/usr/bin/env bash
# ==========================================================================
#  Build de Transcriptor para macOS (.app) y Linux (onedir) con PyInstaller.
#
#  Uso:    scripts/build_unix.sh   (con el venv activado y pyinstaller instalado)
#  Salida: macOS  → dist/Transcriptor.app
#          Linux  → dist/Transcriptor/Transcriptor
#
#  Equivalente POSIX de build_windows.bat: prepara el Python embebido (Opción C)
#  en scripts/embedded_python y corre PyInstaller. Como en macOS/Linux el Python
#  del sistema no es copiable/relocalizable, se usa python-build-standalone
#  (CPython relocalizable, el mismo que usa uv). La versión menor (3.13) DEBE
#  coincidir con la del Python que corre PyInstaller: la stdlib embebida sirve
#  de fallback del bundle (misma ABI).
# ==========================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

PBS_TAG=20260623
PBS_VER=3.13.14

case "$(uname -s)-$(uname -m)" in
  Darwin-arm64) TRIPLE=aarch64-apple-darwin ;;
  Linux-x86_64) TRIPLE=x86_64-unknown-linux-gnu ;;
  *) echo "Plataforma no soportada: $(uname -s)-$(uname -m)" >&2; exit 1 ;;
esac

URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_TAG}/cpython-${PBS_VER}+${PBS_TAG}-${TRIPLE}-install_only_stripped.tar.gz"

echo "Preparando Python embebido desde ${URL} ..."
rm -rf scripts/embedded_python
mkdir -p scripts/embedded_python
curl -fsSL "$URL" | tar -xz -C scripts/embedded_python --strip-components=1

pyinstaller --noconfirm scripts/transcriptor.spec

echo
if [ "$(uname -s)" = "Darwin" ]; then
  echo "Build terminado: dist/Transcriptor.app"
else
  echo "Build terminado: dist/Transcriptor/Transcriptor"
fi
