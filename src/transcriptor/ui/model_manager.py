"""Diálogo gestor de modelos: descarga con progreso estilo "LM Studio".

Muestra el catálogo (`models.registry`), el estado de cada modelo (descargado o
no) y permite descargar el que falte con una barra de progreso de bytes. En el
primer arranque (sin ningún modelo) sugiere el modelo recomendado.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from transcriptor.models import downloader, registry
from transcriptor.workers.download_worker import DownloadWorker

RECOMMENDED_MODEL = "large-v3-turbo"


def _fmt_mb(num_bytes: int) -> str:
    return f"{num_bytes / 1_000_000:.0f} MB"


class ModelManagerDialog(QDialog):
    """Gestiona la descarga de modelos Whisper."""

    def __init__(self, parent: QWidget | None = None, *, first_run: bool = False) -> None:
        super().__init__(parent)
        self.setWindowTitle("Gestor de modelos")
        self.resize(620, 420)

        self._worker: DownloadWorker | None = None
        self._buttons: dict[str, QPushButton] = {}
        self._rows: dict[str, int] = {}

        layout = QVBoxLayout(self)

        intro = QLabel()
        intro.setWordWrap(True)
        if first_run:
            rec = registry.get(RECOMMENDED_MODEL)
            intro.setText(
                "No tienes ningún modelo descargado. Para empezar a transcribir, "
                f"descarga el modelo recomendado: <b>{rec.label}</b>."
            )
        else:
            intro.setText("Descarga o comprueba los modelos de transcripción disponibles.")
        layout.addWidget(intro)

        self._table = QTableWidget(0, 4, self)
        self._table.setHorizontalHeaderLabels(["Modelo", "Tamaño", "Estado", "Acción"])
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for col in (1, 2, 3):
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._table)

        # Barra de progreso + estado (ocultos hasta que empieza una descarga).
        self._status = QLabel("")
        self._status.setVisible(False)
        layout.addWidget(self._status)

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._close_btn = QPushButton("Cerrar")
        self._close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._close_btn)
        layout.addLayout(btn_row)

        self._populate()

    # ------------------------------------------------------------------ tabla

    def _populate(self) -> None:
        models = registry.all_models()
        self._table.setRowCount(len(models))
        for row, info in enumerate(models):
            self._rows[info.model_id] = row
            self._table.setItem(row, 0, QTableWidgetItem(info.label))
            self._table.setItem(row, 1, QTableWidgetItem(f"≈{info.size_mb} MB"))
            self._refresh_row(info.model_id)

    def _refresh_row(self, model_id: str) -> None:
        row = self._rows[model_id]
        done = downloader.is_downloaded(model_id)

        estado = QTableWidgetItem("Descargado" if done else "No descargado")
        self._table.setItem(row, 2, estado)

        btn = QPushButton("Descargado" if done else "Descargar")
        btn.setEnabled(not done)
        btn.clicked.connect(lambda _checked=False, mid=model_id: self._start_download(mid))
        self._buttons[model_id] = btn
        self._table.setCellWidget(row, 3, btn)

    # --------------------------------------------------------------- descarga

    def _set_buttons_enabled(self, enabled: bool) -> None:
        for mid, btn in self._buttons.items():
            btn.setEnabled(enabled and not downloader.is_downloaded(mid))

    def _start_download(self, model_id: str) -> None:
        if self._worker is not None:
            return  # ya hay una descarga en curso

        self._set_buttons_enabled(False)
        self._status.setText(f"Preparando descarga de {registry.get(model_id).label}…")
        self._status.setVisible(True)
        self._progress.setVisible(True)
        self._progress.setRange(0, 100)
        self._progress.setValue(0)

        worker = DownloadWorker(model_id, self)
        worker.status.connect(self._status.setText)
        worker.progress.connect(self._on_progress)
        worker.bytes_progress.connect(self._on_bytes)
        worker.finished_ok.connect(lambda _path, mid=model_id: self._on_done(mid))
        worker.failed.connect(lambda msg, mid=model_id: self._on_failed(mid, msg))
        self._worker = worker
        worker.start()

    def _on_progress(self, pct: int) -> None:
        if pct < 0:
            self._progress.setRange(0, 0)  # total desconocido → barra indeterminada
        else:
            self._progress.setRange(0, 100)
            self._progress.setValue(pct)

    def _on_bytes(self, downloaded: int, total: int) -> None:
        if total > 0:
            self._status.setText(f"Descargando… {_fmt_mb(downloaded)} / {_fmt_mb(total)}")
        else:
            self._status.setText(f"Descargando… {_fmt_mb(downloaded)}")

    def _on_done(self, model_id: str) -> None:
        self._worker = None
        self._progress.setRange(0, 100)
        self._progress.setValue(100)
        self._status.setText(f"{registry.get(model_id).label} descargado.")
        self._refresh_row(model_id)
        self._set_buttons_enabled(True)

    def _on_failed(self, model_id: str, message: str) -> None:
        self._worker = None
        self._progress.setVisible(False)
        self._status.setVisible(False)
        self._set_buttons_enabled(True)
        QMessageBox.critical(
            self,
            "Error al descargar",
            f"No se pudo descargar {registry.get(model_id).label}.\n\n{message}",
        )

    def has_any_model(self) -> bool:
        """True si hay al menos un modelo descargado (para el flujo de arranque)."""
        return any(downloader.is_downloaded(m.model_id) for m in registry.all_models())
