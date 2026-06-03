"""Worker que une los informes de una carpeta en un PDF consolidado.

La generación del PDF (embebido de fuentes + render) supera los 50 ms, así que
va en un QThread para no bloquear la UI.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from transcriptor.report import pdf


class UnifyWorker(QThread):
    """Genera el PDF consolidado de una carpeta.

    Señales:
        finished_ok(str) → ruta del PDF generado.
        failed(str)      → mensaje de error humano.
    """

    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, folder: Path, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._folder = folder

    def run(self) -> None:
        try:
            output = pdf.consolidate(self._folder)
            self.finished_ok.emit(str(output))
        except Exception as e:  # noqa: BLE001 — feedback humano a la UI
            self.failed.emit(str(e))
