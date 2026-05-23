"""Bootstrap de la QApplication."""

from __future__ import annotations

import sys

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from transcriptor.ui.main_window import MainWindow


def main() -> int:
    """Punto de entrada de la app. Devuelve el código de salida del event loop."""
    # Identidad de la app para QSettings (usaremos esto en F1).
    QCoreApplication.setOrganizationName("letzzar")
    QCoreApplication.setOrganizationDomain("letzzar.com")
    QCoreApplication.setApplicationName("Transcriptor")

    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
