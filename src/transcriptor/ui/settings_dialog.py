"""Diálogo de Preferencias.

Cinco bloques:
    - HF_TOKEN (con toggle mostrar/ocultar y botón "Probar token").
    - Ruta de caché de modelos.
    - Idioma forzado para Whisper.
    - Tema (visualmente aplicado en F7).
    - Botones OK / Cancelar.

Al aceptar, persiste todo vía `config.py`.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from transcriptor import config
from transcriptor.workers.token_test_worker import TokenTestWorker


_LANGUAGES: list[tuple[config.Language, str]] = [
    ("auto", "Detectar automáticamente"),
    ("es", "Español"),
    ("en", "Inglés"),
    ("fr", "Francés"),
    ("de", "Alemán"),
    ("it", "Italiano"),
    ("pt", "Portugués"),
    ("ca", "Catalán"),
    ("eu", "Euskera"),
    ("gl", "Gallego"),
]

_THEMES: list[tuple[config.Theme, str]] = [
    ("auto", "Automático (según el SO)"),
    ("claro", "Claro"),
    ("oscuro", "Oscuro"),
]


class SettingsDialog(QDialog):
    """Diálogo modal de Preferencias."""

    def __init__(self, parent: QWidget | None = None, focus_token: bool = False) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferencias")
        self.setMinimumWidth(520)

        self._token_worker: TokenTestWorker | None = None

        root = QVBoxLayout(self)

        root.addWidget(self._build_token_group())
        root.addWidget(self._build_models_group())
        root.addWidget(self._build_transcribe_group())
        root.addWidget(self._build_appearance_group())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        self._load_values()

        if focus_token:
            self.token_edit.setFocus()

    # ------------------------------------------------------------------ UI

    def _build_token_group(self) -> QGroupBox:
        group = QGroupBox("HuggingFace")
        form = QFormLayout(group)

        self.token_edit = QLineEdit()
        self.token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.token_edit.setPlaceholderText("hf_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx")

        self.show_token_chk = QCheckBox("Mostrar")
        self.show_token_chk.toggled.connect(self._on_toggle_show_token)

        token_row = QHBoxLayout()
        token_row.addWidget(self.token_edit, 1)
        token_row.addWidget(self.show_token_chk)
        token_widget = QWidget()
        token_widget.setLayout(token_row)
        form.addRow("Token:", token_widget)

        self.test_btn = QPushButton("Probar token")
        self.test_btn.clicked.connect(self._on_test_token)
        self.test_status = QLabel("")
        self.test_status.setWordWrap(True)

        test_row = QHBoxLayout()
        test_row.addWidget(self.test_btn)
        test_row.addWidget(self.test_status, 1)
        test_widget = QWidget()
        test_widget.setLayout(test_row)
        form.addRow("", test_widget)

        hint = QLabel(
            'Crea un token en <a href="https://huggingface.co/settings/tokens">'
            "huggingface.co/settings/tokens</a> con rol <b>Read</b>. "
            "Necesario para descargar los modelos de pyannote (diarización)."
        )
        hint.setOpenExternalLinks(True)
        hint.setWordWrap(True)
        form.addRow("", hint)

        return group

    def _build_models_group(self) -> QGroupBox:
        group = QGroupBox("Modelos")
        form = QFormLayout(group)

        self.cache_edit = QLineEdit()
        self.cache_edit.setReadOnly(True)

        browse_btn = QPushButton("Examinar…")
        browse_btn.clicked.connect(self._on_browse_cache)
        reset_btn = QPushButton("Predeterminado")
        reset_btn.clicked.connect(self._on_reset_cache)

        row = QHBoxLayout()
        row.addWidget(self.cache_edit, 1)
        row.addWidget(browse_btn)
        row.addWidget(reset_btn)
        wrapper = QWidget()
        wrapper.setLayout(row)
        form.addRow("Caché de modelos:", wrapper)

        return group

    def _build_transcribe_group(self) -> QGroupBox:
        group = QGroupBox("Transcripción")
        form = QFormLayout(group)

        self.language_combo = QComboBox()
        for value, label in _LANGUAGES:
            self.language_combo.addItem(label, value)
        form.addRow("Idioma:", self.language_combo)

        return group

    def _build_appearance_group(self) -> QGroupBox:
        group = QGroupBox("Apariencia")
        form = QFormLayout(group)

        self.theme_combo = QComboBox()
        for value, label in _THEMES:
            self.theme_combo.addItem(label, value)
        form.addRow("Tema:", self.theme_combo)

        return group

    # --------------------------------------------------------------- estado

    def _load_values(self) -> None:
        token = config.get_hf_token() or ""
        self.token_edit.setText(token)

        self.cache_edit.setText(str(config.get_models_cache_dir()))

        current_lang = config.get_language()
        idx = self.language_combo.findData(current_lang)
        self.language_combo.setCurrentIndex(max(0, idx))

        current_theme = config.get_theme()
        idx = self.theme_combo.findData(current_theme)
        self.theme_combo.setCurrentIndex(max(0, idx))

    def _on_accept(self) -> None:
        config.set_hf_token(self.token_edit.text())
        cache_value = self.cache_edit.text().strip()
        default_cache = str(config.default_models_cache_dir())
        config.set_models_cache_dir(None if cache_value == default_cache else cache_value)
        config.set_language(self.language_combo.currentData())
        config.set_theme(self.theme_combo.currentData())
        self.accept()

    # --------------------------------------------------------------- handlers

    def _on_toggle_show_token(self, checked: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
        self.token_edit.setEchoMode(mode)

    def _on_browse_cache(self) -> None:
        current = self.cache_edit.text() or str(Path.home())
        chosen = QFileDialog.getExistingDirectory(self, "Carpeta de caché de modelos", current)
        if chosen:
            self.cache_edit.setText(chosen)

    def _on_reset_cache(self) -> None:
        self.cache_edit.setText(str(config.default_models_cache_dir()))

    def _on_test_token(self) -> None:
        token = self.token_edit.text().strip()
        if not token:
            self._set_test_status(False, "Introduce un token primero.")
            return

        self.test_btn.setEnabled(False)
        self._set_test_status(None, "Comprobando…")

        worker = TokenTestWorker(token, parent=self)
        worker.result.connect(self._on_token_tested)
        worker.finished.connect(self._on_token_test_finished)
        self._token_worker = worker
        worker.start()

    def _on_token_tested(self, ok: bool, message: str) -> None:
        if ok:
            self._set_test_status(True, f"Token válido. Usuario: {message}.")
        else:
            self._set_test_status(False, message)

    def _on_token_test_finished(self) -> None:
        self.test_btn.setEnabled(True)
        self._token_worker = None

    def _set_test_status(self, ok: bool | None, text: str) -> None:
        self.test_status.setText(text)
        if ok is True:
            self.test_status.setStyleSheet("color: #2e7d32;")  # verde
        elif ok is False:
            self.test_status.setStyleSheet("color: #c62828;")  # rojo
        else:
            self.test_status.setStyleSheet("color: gray;")
