"""Bootstrap de la QApplication."""

from __future__ import annotations

import sys

from PySide6.QtCore import QCoreApplication, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon
from PySide6.QtWidgets import QApplication, QMessageBox, QProgressDialog

from transcriptor import config
from transcriptor.runtime import ffmpeg_setup, provision
from transcriptor.ui.first_run import FirstRunDialog
from transcriptor.ui.resources import app_icon_path
from transcriptor.ui.theme import apply_theme
from transcriptor.workers.ffmpeg_worker import FfmpegInstallWorker


def main() -> int:
    """Punto de entrada de la app. Devuelve el código de salida del event loop."""
    # Identidad de la app para QSettings (usaremos esto en F1).
    QCoreApplication.setOrganizationName("letzzar")
    QCoreApplication.setOrganizationDomain("letzzar.com")
    QCoreApplication.setApplicationName("Transcriptor")

    app = QApplication(sys.argv)
    icon_path = app_icon_path()
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    apply_theme(app, config.get_theme())

    # Primer arranque: descargar el backend (torch + motores) adaptado al
    # equipo. Si ya está, `activate()` solo lo añade a sys.path. Si el usuario
    # cancela la preparación, salimos (el motor es imprescindible).
    provision.activate()
    if not provision.is_provisioned():
        dialog = FirstRunDialog()
        dialog.exec()
        if not dialog.succeeded():
            return 0
        provision.activate()

    if "--selftest" in sys.argv:
        return _selftest()

    _ensure_ffmpeg()

    # Import diferido: MainWindow arrastra tqdm/huggingface_hub, que deben
    # resolverse desde el venv del backend (ya en sys.path tras activate()), no
    # desde las copias parciales del bundle. Importar antes los congelaría.
    from transcriptor.ui.main_window import MainWindow

    window = MainWindow()
    window.show()
    return app.exec()


def _selftest() -> int:
    """Diagnóstico oculto (`Transcriptor.exe --selftest`).

    Con el backend ya activado, ejecuta la cadena de imports que históricamente
    fallaba en el bundle congelado y escribe el resultado a un archivo (la app
    es --windowed, sin consola). Sirve para validar el empaquetado sin depender
    de la GPU.
    """
    import tempfile
    import traceback
    from pathlib import Path

    out = Path(tempfile.gettempdir()) / "transcriptor_selftest.txt"
    lines: list[str] = []
    try:
        import tqdm.contrib.logging  # type: ignore[import-untyped]  # noqa: F401
        lines.append("tqdm.contrib.logging OK")
        from pyannote.audio import Pipeline  # noqa: F401
        lines.append("pyannote.audio.Pipeline OK")
        import torch
        lines.append(f"torch {torch.__version__} cuda={torch.cuda.is_available()}")
        lines.append("SELFTEST OK")
    except Exception:  # noqa: BLE001 — queremos la traza completa en el archivo
        lines.append("SELFTEST FAILED")
        lines.append(traceback.format_exc())
    out.write_text("\n".join(lines), encoding="utf-8")
    return 0


def _ensure_ffmpeg() -> None:
    """Comprueba FFmpeg al arrancar; si falta, ofrece instalarlo con winget.

    Si el usuario acepta, instala `Gyan.FFmpeg` con winget (progreso modal). Si
    no quiere, o winget falla, abre la web oficial de FFmpeg.
    """
    from transcriptor.pipeline.audio import find_ffmpeg

    if find_ffmpeg() is not None:
        return

    answer = QMessageBox.question(
        None,
        "FFmpeg no encontrado",
        "Transcriptor necesita FFmpeg para procesar el audio y no está "
        "instalado.\n\n¿Quieres instalarlo ahora automáticamente (winget)?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    )
    if answer != QMessageBox.StandardButton.Yes:
        QDesktopServices.openUrl(QUrl(ffmpeg_setup.FFMPEG_URL))
        return

    progress = QProgressDialog("Instalando FFmpeg con winget…", "", 0, 0, None)
    progress.setWindowTitle("Instalando FFmpeg")
    progress.setCancelButton(None)
    progress.setWindowModality(Qt.WindowModality.ApplicationModal)
    progress.setMinimumDuration(0)

    worker = FfmpegInstallWorker()
    result = {"ok": False}

    def _on_done(ok: bool) -> None:  # noqa: FBT001
        result["ok"] = ok
        progress.close()

    worker.finished_ok.connect(_on_done)
    worker.start()
    progress.exec()
    worker.wait()

    if result["ok"]:
        ffmpeg_setup.refresh_path_from_registry()
        if find_ffmpeg() is not None:
            QMessageBox.information(None, "FFmpeg", "FFmpeg se instaló correctamente.")
        else:
            QMessageBox.information(
                None,
                "FFmpeg",
                "FFmpeg se instaló. Reinicia Transcriptor para que surta efecto.",
            )
    else:
        QMessageBox.warning(
            None,
            "FFmpeg",
            "No se pudo instalar FFmpeg automáticamente. Abriremos la web para "
            "instalarlo manualmente.",
        )
        QDesktopServices.openUrl(QUrl(ffmpeg_setup.FFMPEG_URL))
