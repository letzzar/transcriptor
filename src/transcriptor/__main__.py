"""Punto de entrada: `python -m transcriptor`."""

from __future__ import annotations

import os
import sys

# En el bundle PyInstaller --windowed (console=False), sys.stdout/stderr son
# None. Cualquier escritura (la barra tqdm de las descargas de modelos, prints
# de librerias) lanzaria "'NoneType' object has no attribute 'write'". Los
# redirigimos a un sink ANTES de importar nada que pueda escribir.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w", encoding="utf-8")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w", encoding="utf-8")

from transcriptor.app import main  # noqa: E402  (tras asegurar los streams)


if __name__ == "__main__":
    sys.exit(main())
