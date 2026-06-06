"""Ventana principal de la aplicación.

Controles (PROYECTO.md §8.1): selección de carpeta, modelo, nº de hablantes,
limpieza de audio, botón Transcribir, barra de progreso, estado y panel de
logs. La transcripción corre en `TranscribeWorker` (QThread); la UI nunca se
bloquea.

Flujo de primer arranque: sin token → Preferencias; con token y sin modelos →
Gestor de modelos sugiriendo el recomendado.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from transcriptor import __version__, config
from transcriptor.models import downloader, registry
from transcriptor.platform_info import detect_engine, detect_os, engine_label
from transcriptor.ui.model_manager import RECOMMENDED_MODEL, ModelManagerDialog
from transcriptor.ui.settings_dialog import SettingsDialog
from transcriptor.workers.transcribe_worker import TranscribeWorker
from transcriptor.workers.unify_worker import UnifyWorker


class MainWindow(QMainWindow):
    """Ventana principal."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"Transcriptor {__version__}")
        self.resize(900, 680)

        self._folder: Path | None = config.get_last_folder()
        self._worker: TranscribeWorker | None = None
        self._unify_worker: UnifyWorker | None = None

        self._build_central()
        self._build_menu()
        self._refresh_models()
        self._update_folder_label()

        # Primer arranque: sin token → Settings; con token y sin modelos → Gestor.
        if not config.get_hf_token():
            QTimer.singleShot(0, lambda: self.open_settings(focus_token=True))
        elif not self._has_any_model():
            QTimer.singleShot(0, lambda: self.open_model_manager(first_run=True))

    # ------------------------------------------------------------------ UI

    def _build_central(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)

        engine = detect_engine()
        self.engine_label = QLabel(
            f"Sistema: {detect_os()}  ·  Motor: {engine_label(engine)}"
        )
        self.engine_label.setStyleSheet("color: gray;")
        layout.addWidget(self.engine_label)

        # Carpeta de audios
        folder_row = QHBoxLayout()
        self.btn_folder = QPushButton("Seleccionar carpeta…")
        self.btn_folder.clicked.connect(self._select_folder)
        folder_row.addWidget(self.btn_folder)
        self.lbl_folder = QLabel("Ninguna carpeta seleccionada")
        self.lbl_folder.setWordWrap(True)
        folder_row.addWidget(self.lbl_folder, stretch=1)
        layout.addLayout(folder_row)

        # Modelo
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Modelo:"))
        self.cmb_model = QComboBox()
        model_row.addWidget(self.cmb_model, stretch=1)
        self.btn_manage = QPushButton("Gestionar modelos…")
        self.btn_manage.clicked.connect(lambda: self.open_model_manager(first_run=False))
        model_row.addWidget(self.btn_manage)
        layout.addLayout(model_row)

        # Hablantes + limpieza
        opts_row = QHBoxLayout()
        self.chk_auto_speakers = QPushButton("Auto-detectar hablantes")
        self.chk_auto_speakers.setCheckable(True)
        self.chk_auto_speakers.setChecked(True)
        self.chk_auto_speakers.toggled.connect(self._on_auto_speakers_toggled)
        opts_row.addWidget(self.chk_auto_speakers)
        opts_row.addWidget(QLabel("Máx.:"))
        self.spin_speakers = QSpinBox()
        self.spin_speakers.setRange(2, 5)
        self.spin_speakers.setValue(2)
        self.spin_speakers.setEnabled(False)  # deshabilitado mientras Auto está activo
        opts_row.addWidget(self.spin_speakers)
        opts_row.addSpacing(20)
        self.chk_clean = QPushButton("Limpiar audio (FFmpeg)")
        self.chk_clean.setCheckable(True)
        opts_row.addWidget(self.chk_clean)
        self.chk_gender = QPushButton("Estimar género de las voces")
        self.chk_gender.setCheckable(True)
        self.chk_gender.setChecked(True)
        self.chk_gender.setToolTip(
            "Estima el género de cada voz con un modelo (descarga ~1 GB la 1ª vez). "
            "Es una estimación; se etiqueta como 'probable'."
        )
        opts_row.addWidget(self.chk_gender)
        opts_row.addStretch()
        layout.addLayout(opts_row)

        # Botones de acción
        action_row = QHBoxLayout()
        self.btn_transcribe = QPushButton("Transcribir")
        self.btn_transcribe.clicked.connect(self._start_transcription)
        action_row.addWidget(self.btn_transcribe, stretch=1)
        self.btn_unify = QPushButton("Unificar reportes (PDF)")
        self.btn_unify.clicked.connect(self._start_unify)
        action_row.addWidget(self.btn_unify, stretch=1)
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self._cancel_transcription)
        self.btn_cancel.setVisible(False)
        action_row.addWidget(self.btn_cancel)
        layout.addLayout(action_row)

        # Estado + progreso
        self.lbl_status = QLabel("")
        layout.addWidget(self.lbl_status)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        # Panel de logs (colapsable)
        self.btn_logs = QPushButton("Mostrar logs")
        self.btn_logs.setCheckable(True)
        self.btn_logs.toggled.connect(self._toggle_logs)
        layout.addWidget(self.btn_logs)
        self.txt_logs = QPlainTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setVisible(False)
        layout.addWidget(self.txt_logs, stretch=1)

        self.setCentralWidget(central)

    def _build_menu(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&Archivo")

        open_action = QAction("Abrir carpeta…", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)  # Ctrl/Cmd+O
        open_action.triggered.connect(self._select_folder)
        file_menu.addAction(open_action)

        self.transcribe_action = QAction("Transcribir", self)
        self.transcribe_action.setShortcut("Ctrl+R")
        self.transcribe_action.triggered.connect(self._start_transcription)
        file_menu.addAction(self.transcribe_action)

        self.unify_action = QAction("Unificar reportes (PDF)", self)
        self.unify_action.triggered.connect(self._start_unify)
        file_menu.addAction(self.unify_action)

        file_menu.addSeparator()

        # En macOS, Qt mueve "Preferencias…" al menú de la app por PreferencesRole.
        prefs_action = QAction("Preferencias…", self)
        prefs_action.setShortcut(QKeySequence.StandardKey.Preferences)
        prefs_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        prefs_action.triggered.connect(lambda: self.open_settings(focus_token=False))
        file_menu.addAction(prefs_action)

        quit_action = QAction("Salir", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.setMenuRole(QAction.MenuRole.QuitRole)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        models_menu = menubar.addMenu("&Modelos")
        manage_action = QAction("Gestionar modelos…", self)
        manage_action.triggered.connect(lambda: self.open_model_manager(first_run=False))
        models_menu.addAction(manage_action)

    # ----------------------------------------------------------------- estado

    def _refresh_models(self) -> None:
        """Rellena el combo solo con los modelos ya descargados."""
        current = self.cmb_model.currentData()
        self.cmb_model.clear()
        for info in registry.all_models():
            if downloader.is_downloaded(info.model_id):
                self.cmb_model.addItem(info.label, info.model_id)

        # Restaura selección: la actual, la preferida, la recomendada o la 1ª.
        preferred = current or config.get_preferred_model() or RECOMMENDED_MODEL
        idx = self.cmb_model.findData(preferred)
        if idx >= 0:
            self.cmb_model.setCurrentIndex(idx)

        has_models = self.cmb_model.count() > 0
        self.cmb_model.setEnabled(has_models)
        if not has_models:
            self.cmb_model.addItem("(sin modelos descargados)", None)

    def _update_folder_label(self) -> None:
        if self._folder:
            self.lbl_folder.setText(str(self._folder))
        else:
            self.lbl_folder.setText("Ninguna carpeta seleccionada")

    def _set_running(self, running: bool) -> None:
        self.btn_transcribe.setEnabled(not running)
        self.transcribe_action.setEnabled(not running)
        self.btn_unify.setEnabled(not running)
        self.unify_action.setEnabled(not running)
        self.btn_folder.setEnabled(not running)
        self.btn_manage.setEnabled(not running)
        self.cmb_model.setEnabled(not running and self.cmb_model.count() > 0)
        self.chk_auto_speakers.setEnabled(not running)
        self.spin_speakers.setEnabled(not running and not self.chk_auto_speakers.isChecked())
        self.chk_clean.setEnabled(not running)
        self.chk_gender.setEnabled(not running)
        self.btn_cancel.setVisible(running)

    # ----------------------------------------------------------------- slots

    def _on_auto_speakers_toggled(self, checked: bool) -> None:
        # En modo Auto, el nº de hablantes lo decide la diarización; deshabilita
        # el límite manual.
        self.spin_speakers.setEnabled(not checked)

    def _select_folder(self) -> None:
        start = str(self._folder) if self._folder else ""
        chosen = QFileDialog.getExistingDirectory(self, "Selecciona la carpeta de audios", start)
        if chosen:
            self._folder = Path(chosen)
            config.set_last_folder(self._folder)
            self._update_folder_label()

    def _toggle_logs(self, checked: bool) -> None:
        self.txt_logs.setVisible(checked)
        self.btn_logs.setText("Ocultar logs" if checked else "Mostrar logs")

    def _append_log(self, line: str) -> None:
        self.txt_logs.appendPlainText(line)

    def _start_transcription(self) -> None:
        if self._worker is not None:
            return
        if not self._folder or not self._folder.exists():
            QMessageBox.warning(self, "Falta carpeta", "Selecciona primero una carpeta de audios.")
            return
        model_id = self.cmb_model.currentData()
        if not model_id:
            QMessageBox.warning(
                self,
                "Falta modelo",
                "No hay ningún modelo descargado. Abre 'Gestionar modelos…' para descargar uno.",
            )
            return

        config.set_preferred_model(model_id)
        language = config.get_language()
        self.txt_logs.clear()
        if not self.btn_logs.isChecked():
            self.btn_logs.setChecked(True)
        self.progress.setValue(0)

        # Auto → None (la diarización decide); manual → el tope del spinbox.
        max_speakers = None if self.chk_auto_speakers.isChecked() else self.spin_speakers.value()
        worker = TranscribeWorker(
            self._folder,
            model_id=model_id,
            max_speakers=max_speakers,
            enhance=self.chk_clean.isChecked(),
            language=None if language == "auto" else language,
            detect_gender=self.chk_gender.isChecked(),
            parent=self,
        )
        worker.status.connect(self.lbl_status.setText)
        worker.log.connect(self._append_log)
        worker.progress.connect(self.progress.setValue)
        worker.finished_ok.connect(self._on_finished)
        worker.failed.connect(self._on_failed)
        self._worker = worker
        self._set_running(True)
        worker.start()

    def _cancel_transcription(self) -> None:
        if self._worker is not None:
            self._worker.requestInterruption()
            self.lbl_status.setText("Cancelando tras el archivo actual…")

    def _on_finished(self, count: int) -> None:
        self._worker = None
        self._set_running(False)
        self.lbl_status.setText(f"Listo. {count} archivo(s) transcrito(s).")
        QMessageBox.information(
            self, "Transcripción terminada", f"Se transcribieron {count} archivo(s)."
        )

    def _on_failed(self, message: str) -> None:
        self._worker = None
        self._set_running(False)
        self.lbl_status.setText("Error.")
        QMessageBox.critical(self, "Error de transcripción", message)

    # ----------------------------------------------------------------- unificar

    def _start_unify(self) -> None:
        if self._unify_worker is not None or self._worker is not None:
            return
        if not self._folder or not self._folder.exists():
            QMessageBox.warning(self, "Falta carpeta", "Selecciona primero una carpeta.")
            return

        self.lbl_status.setText("Generando PDF consolidado…")
        worker = UnifyWorker(self._folder, self)
        worker.finished_ok.connect(self._on_unify_done)
        worker.failed.connect(self._on_unify_failed)
        self._unify_worker = worker
        self._set_running(True)
        worker.start()

    def _on_unify_done(self, pdf_path: str) -> None:
        self._unify_worker = None
        self._set_running(False)
        self.lbl_status.setText(f"PDF generado: {Path(pdf_path).name}")
        if self._folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._folder)))
        QMessageBox.information(
            self, "Reportes unificados", f"Se generó el PDF:\n{pdf_path}"
        )

    def _on_unify_failed(self, message: str) -> None:
        self._unify_worker = None
        self._set_running(False)
        self.lbl_status.setText("Error.")
        QMessageBox.warning(self, "No se pudo unificar", message)

    # ----------------------------------------------------------------- diálogos

    def open_settings(self, focus_token: bool = False) -> None:
        dlg = SettingsDialog(self, focus_token=focus_token)
        dlg.exec()

    def open_model_manager(self, first_run: bool = False) -> None:
        dlg = ModelManagerDialog(self, first_run=first_run)
        dlg.exec()
        self._refresh_models()  # por si se descargó alguno nuevo

    def _has_any_model(self) -> bool:
        """True si hay al menos un modelo descargado en la caché."""
        return any(downloader.is_downloaded(m.model_id) for m in registry.all_models())
