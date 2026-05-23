"""Ventana principal de la aplicación.

F0: ventana vacía con título y un indicador del motor Whisper detectado.
F1: menú "Preferencias…" (Ctrl/Cmd+,). Si no hay HF_TOKEN al arrancar,
    abre el diálogo de Settings con foco en el campo.
Los bloques de carpeta, modelo, hablantes, progreso y logs se añaden en
fases posteriores del roadmap (ver PROYECTO.md §8.1).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QVBoxLayout,
    QWidget,
)

from transcriptor import __version__, config
from transcriptor.platform import detect_engine, detect_os, engine_label
from transcriptor.ui.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    """Ventana principal."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"Transcriptor {__version__}")
        self.resize(900, 600)

        self._build_central()
        self._build_menu()

        # Si no hay token al arrancar, abrimos Settings tras mostrarse la ventana.
        # Se usa singleShot para que el showEvent termine antes y evitar parpadeos.
        if not config.get_hf_token():
            QTimer.singleShot(0, lambda: self.open_settings(focus_token=True))

    # ------------------------------------------------------------------ UI

    def _build_central(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("Transcriptor")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_font = title.font()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title.setFont(title_font)
        layout.addWidget(title)

        engine = detect_engine()
        self.engine_label = QLabel(
            f"Sistema operativo: {detect_os()}\n"
            f"Motor recomendado: {engine_label(engine)}"
        )
        self.engine_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.engine_label)

        placeholder = QLabel(
            "Esqueleto inicial.\n"
            "Funcionalidad pendiente en próximas fases."
        )
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        placeholder.setStyleSheet("color: gray;")
        layout.addWidget(placeholder)

        self.setCentralWidget(central)

    def _build_menu(self) -> None:
        menubar = self.menuBar()

        # En macOS, Qt mueve "Preferencias…" automáticamente al menú de la app
        # cuando la acción tiene role PreferencesRole.
        file_menu = menubar.addMenu("&Archivo")

        prefs_action = QAction("Preferencias…", self)
        prefs_action.setShortcut(QKeySequence.StandardKey.Preferences)
        prefs_action.setMenuRole(QAction.MenuRole.PreferencesRole)
        prefs_action.triggered.connect(lambda: self.open_settings(focus_token=False))
        file_menu.addAction(prefs_action)

        file_menu.addSeparator()

        quit_action = QAction("Salir", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.setMenuRole(QAction.MenuRole.QuitRole)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    # ----------------------------------------------------------------- slots

    def open_settings(self, focus_token: bool = False) -> None:
        dlg = SettingsDialog(self, focus_token=focus_token)
        dlg.exec()
