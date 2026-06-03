"""Smoke test E2E del TranscribeWorker (F4c).

Recibe la ruta de UN audio por argumento, lo copia a una carpeta temporal,
ejecuta el pipeline completo (audio → diarización → transcripción → merge →
informe) vía `TranscribeWorker.run()` de forma síncrona y comprueba que se
generan los informes. Solo imprime METADATOS (nunca el texto transcrito).

Uso:
    python tests/smoke_pipeline.py "ruta\\al\\audio.m4a" [max_speakers]
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from PySide6.QtWidgets import QApplication

from transcriptor.report.txt import ANALYSIS_SUFFIX, SUMMARY_FILENAME
from transcriptor.workers.transcribe_worker import TranscribeWorker

_SPEAKER_RE = re.compile(r"^\[\d\d:\d\d\] \(([^)]+)\):")


def main() -> int:
    if len(sys.argv) < 2:
        print("Uso: python tests/smoke_pipeline.py <audio> [max_speakers]")
        return 2
    src = Path(sys.argv[1])
    max_speakers = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    if not src.exists():
        print(f"No existe el audio: {src}")
        return 1

    _app = QApplication([])  # necesario para QThread/QObject
    work_dir = Path(tempfile.mkdtemp(prefix="transcriptor_smoke_"))
    try:
        shutil.copy2(src, work_dir / src.name)

        worker = TranscribeWorker(
            work_dir,
            model_id="tiny",  # rápido para el smoke
            max_speakers=max_speakers,
            enhance=False,
            language=None,
        )
        worker.log.connect(lambda s: print("  log:", s))
        worker.status.connect(lambda s: print("  estado:", s))
        worker.run()  # síncrono (mismo hilo)

        analysis = list(work_dir.glob(f"*{ANALYSIS_SUFFIX}"))
        summary = work_dir / SUMMARY_FILENAME
        print(f"\nInformes _ANALIZADO: {len(analysis)} | resumen: {summary.exists()}")

        if not analysis:
            print("FAIL: no se generó ningún informe.")
            return 1

        # Metadatos del informe: nº de líneas de segmento y etiquetas de hablante
        # (sin imprimir el texto transcrito).
        speakers: set[str] = set()
        seg_lines = 0
        for line in analysis[0].read_text(encoding="utf-8").splitlines():
            m = _SPEAKER_RE.match(line)
            if m:
                seg_lines += 1
                speakers.add(m.group(1))
        print(f"Segmentos con timestamp+hablante: {seg_lines}")
        print(f"Etiquetas de hablante usadas: {sorted(speakers)}")
        print("(No se muestra texto transcrito — solo metadatos.)")

        print("\nOK — smoke test del pipeline E2E superado.")
        return 0
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
