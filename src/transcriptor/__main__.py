"""Punto de entrada: `python -m transcriptor`."""

from __future__ import annotations

import multiprocessing
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

# En el bundle, `multiprocessing` lanza sus procesos auxiliares (p. ej. el
# resource tracker que arranca tqdm al descargar/verificar un modelo) relanzando
# `sys.executable`, que aquí es la PROPIA app: sin esto, cada uno abría otra
# ventana de Transcriptor. Ejecuta el auxiliar y sale; fuera del bundle, no-op.
multiprocessing.freeze_support()

from transcriptor.app import main  # noqa: E402  (tras asegurar los streams)


if __name__ == "__main__":
    sys.exit(main())
