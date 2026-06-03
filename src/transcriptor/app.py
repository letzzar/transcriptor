"""Bootstrap de la QApplication."""

from __future__ import annotations

import sys

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from transcriptor import config
from transcriptor.ui.main_window import MainWindow
from transcriptor.ui.resources import app_icon_path
from transcriptor.ui.theme import apply_theme


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
    window = MainWindow()
    window.show()
    return app.exec()
