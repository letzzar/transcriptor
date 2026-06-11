"""Worker que provisiona el backend pesado (torch + motores) en segundo plano.

Envuelve `runtime.provision.provision` en un `QThread` para no bloquear la UI
durante la descarga (~2 GB la primera vez). pip no expone un porcentaje fiable,
así que reemitimos sus líneas de salida como log; el progreso se muestra
indeterminado en el diálogo.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

from transcriptor.runtime import provision


class ProvisionWorker(QThread):
    """Instala el backend y emite log/resultado.

    Señales:
        log(str)          → cada línea de salida de pip.
        finished_ok(str)  → variante instalada (`"cu124"` / `"cpu"`).
        failed(str)       → mensaje de error humano si falla.
    """

    log = Signal(str)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, *, gpu: bool, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._gpu = gpu

    def run(self) -> None:
        try:
            variant = provision.provision(gpu=self._gpu, on_line=self.log.emit)
            self.finished_ok.emit(variant)
        except Exception as e:  # noqa: BLE001 — feedback humano al usuario
            self.failed.emit(str(e))
