"""Worker que descarga un modelo en segundo plano emitiendo progreso a la UI.

Envuelve `models.downloader.download` inyectando un `tqdm` personalizado que
captura los bytes descargados (de las barras con `unit == "B"`) y los reemite
como señales Qt, para pintar una barra de progreso estilo "LM Studio".
"""

from __future__ import annotations

from threading import Lock
from typing import Callable

from PySide6.QtCore import QObject, QThread, Signal
from tqdm import tqdm

from transcriptor.models import downloader


def _make_tqdm_class(on_bytes: Callable[[int], None]) -> type[tqdm]:
    """Crea una subclase de tqdm que reporta los bytes de las barras de descarga.

    `snapshot_download` instancia esta clase para cada archivo (y para la barra
    exterior de "Fetching files"). Solo nos interesan las de bytes (`unit=="B"`).
    """

    class _ProgressTqdm(tqdm):  # type: ignore[misc]
        def update(self, n: float | None = 1) -> bool | None:
            if getattr(self, "unit", None) == "B" and n:
                on_bytes(int(n))
            return super().update(n)  # type: ignore[no-any-return]

    return _ProgressTqdm


class DownloadWorker(QThread):
    """Descarga un modelo y emite el progreso.

    Señales:
        progress(int)         → porcentaje 0-100 (o -1 si el total es desconocido).
        bytes_progress(i64,i64) → (bytes_descargados, bytes_totales).
        status(str)           → mensaje de estado para la UI.
        finished_ok(str)      → ruta local del snapshot al terminar.
        failed(str)           → mensaje de error humano si falla.
    """

    progress = Signal(int)
    bytes_progress = Signal("qint64", "qint64")  # type: ignore[arg-type]
    status = Signal(str)
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, model_id: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._model_id = model_id
        self._downloaded = 0
        self._total = 0
        self._last_pct = -1
        self._lock = Lock()

    def _on_bytes(self, n: int) -> None:
        with self._lock:
            self._downloaded += n
            downloaded = self._downloaded
        if self._total > 0:
            pct = min(int(downloaded * 100 / self._total), 100)
            if pct != self._last_pct:
                self._last_pct = pct
                self.progress.emit(pct)
                self.bytes_progress.emit(downloaded, self._total)
        else:
            self.progress.emit(-1)
            self.bytes_progress.emit(downloaded, 0)

    def run(self) -> None:
        try:
            self.status.emit("Calculando tamaño…")
            self._total = downloader.total_size_bytes(self._model_id) or 0
            self.status.emit("Descargando…")
            tqdm_class = _make_tqdm_class(self._on_bytes)
            path = downloader.download(self._model_id, tqdm_class=tqdm_class)
            self.progress.emit(100)
            self.finished_ok.emit(str(path))
        except Exception as e:  # noqa: BLE001 — feedback humano al usuario
            self.failed.emit(str(e))
