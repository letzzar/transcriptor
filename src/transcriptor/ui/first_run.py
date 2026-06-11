"""Diálogo de primer arranque: descarga el backend adaptado al equipo.

Se muestra una sola vez (mientras no exista el marcador de
`runtime.provision`). Detecta la GPU, explica qué se va a instalar (CUDA o CPU)
y lanza la descarga en un `ProvisionWorker`, con log en vivo y progreso
indeterminado. Al terminar con éxito, `succeeded()` devuelve True y la app
continúa al arranque normal.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from transcriptor.runtime import provision
from transcriptor.workers.provision_worker import ProvisionWorker


class FirstRunDialog(QDialog):
    """Asistente de preparación del motor en el primer arranque."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preparar Transcriptor")
        self.setModal(True)
        self.resize(640, 460)

        self._worker: ProvisionWorker | None = None
        self._ok = False
        self._gpu = provision.detect_gpu()

        layout = QVBoxLayout(self)

        self._offline = provision.offline_wheelhouse() is not None
        variant = "CUDA (GPU NVIDIA)" if self._gpu else "CPU"
        if self._offline:
            intro = QLabel(
                "La primera vez, Transcriptor prepara su motor de transcripción "
                "adaptado a tu equipo, desde los componentes ya incluidos (sin "
                "internet).<br><br>"
                f"Equipo detectado: <b>{variant}</b>.<br>"
                "Solo ocurre una vez."
            )
        else:
            intro = QLabel(
                "La primera vez, Transcriptor descarga su motor de transcripción "
                "adaptado a tu equipo.<br><br>"
                f"Equipo detectado: <b>{variant}</b>.<br>"
                "Descarga aproximada: ~2 GB. Solo ocurre una vez."
            )
        intro.setTextFormat(Qt.TextFormat.RichText)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view, 1)

        buttons = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_install = QPushButton("Instalar" if self._offline else "Descargar e instalar")
        self.btn_install.setDefault(True)
        buttons.addStretch(1)
        buttons.addWidget(self.btn_cancel)
        buttons.addWidget(self.btn_install)
        layout.addLayout(buttons)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_install.clicked.connect(self._start)

    def succeeded(self) -> bool:
        """True si el backend quedó instalado correctamente."""
        return self._ok

    def _running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def _start(self) -> None:
        self.btn_install.setEnabled(False)
        self.btn_cancel.setEnabled(False)
        self.progress.setRange(0, 0)  # indeterminado mientras instala
        self._append("Preparando el motor…" if self._offline else "Iniciando descarga…")

        worker = ProvisionWorker(gpu=self._gpu, parent=self)
        worker.log.connect(self._append)
        worker.finished_ok.connect(self._on_ok)
        worker.failed.connect(self._on_failed)
        self._worker = worker
        worker.start()

    def _append(self, line: str) -> None:
        self.log_view.appendPlainText(line)

    def _on_ok(self, variant: str) -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(100)
        self._append(f"Listo (variante {variant}).")
        self._ok = True
        self.accept()

    def _on_failed(self, msg: str) -> None:
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self._append(f"ERROR: {msg}")
        self.btn_install.setEnabled(True)
        self.btn_cancel.setEnabled(True)
        QMessageBox.critical(self, "Error al preparar el motor", msg)

    # No permitir cerrar/cancelar mientras la instalación está en curso.
    def reject(self) -> None:
        if self._running():
            return
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._running():
            event.ignore()
            return
        super().closeEvent(event)
