"""Worker que instala FFmpeg con winget en segundo plano (no bloquea la UI)."""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

from transcriptor.runtime import ffmpeg_setup


class FfmpegInstallWorker(QThread):
    """Ejecuta `winget install Gyan.FFmpeg`.

    Señales:
        log(str)          → líneas de salida de winget.
        finished_ok(bool) → True si winget terminó con éxito.
    """

    log = Signal(str)
    finished_ok = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

    def run(self) -> None:
        ok = ffmpeg_setup.install_with_winget(on_line=self.log.emit)
        self.finished_ok.emit(ok)
