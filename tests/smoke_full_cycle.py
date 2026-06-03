"""Smoke E2E del ciclo completo (transcribir carpeta + unificar PDF).

Recibe una CARPETA y un modelo por argumento. Ejecuta `TranscribeWorker` sobre
todos sus audios y luego `report.pdf.consolidate`. Solo imprime METADATOS
(nunca el texto transcrito).

Uso:
    python tests/smoke_full_cycle.py "D:\\ruta\\carpeta" [modelo] [max_speakers]
"""

from __future__ import annotations

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from PySide6.QtWidgets import QApplication

from transcriptor.report import pdf
from transcriptor.workers.transcribe_worker import TranscribeWorker


def main() -> int:
    if len(sys.argv) < 2:
        print("Uso: python tests/smoke_full_cycle.py <carpeta> [modelo] [max_speakers]")
        return 2
    folder = Path(sys.argv[1])
    model_id = sys.argv[2] if len(sys.argv) > 2 else "base"
    max_speakers = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    if not folder.is_dir():
        print(f"No es una carpeta: {folder}")
        return 1

    _app = QApplication([])

    print(f"== Transcribiendo {folder} con modelo '{model_id}' ==")
    worker = TranscribeWorker(
        folder, model_id=model_id, max_speakers=max_speakers, enhance=False, language=None
    )
    worker.log.connect(lambda s: print("  log:", s))
    worker.finished_ok.connect(lambda n: print(f"== Transcripción terminada: {n} archivo(s) =="))
    worker.run()

    print("\n== Unificando reportes en PDF ==")
    try:
        pdf_path = pdf.consolidate(folder)
    except pdf.ReportError as e:
        print(f"FAIL: {e}")
        return 1

    procesados = folder / "PROCESADOS"
    n_proc = len(list(procesados.glob("*.txt"))) if procesados.exists() else 0
    print(f"PDF generado: {pdf_path.name} ({pdf_path.stat().st_size / 1024:.1f} KB)")
    print(f"Informes archivados en PROCESADOS/: {n_proc}")
    print("(No se muestra texto transcrito — solo metadatos.)")
    print("\nOK — ciclo completo superado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
