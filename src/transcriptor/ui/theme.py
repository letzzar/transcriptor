"""Tema claro/oscuro de la aplicación (estilo Fusion + paleta).

`apply_theme(app, theme)` aplica el tema elegido:
    - "claro"  → paleta clara estándar.
    - "oscuro" → paleta oscura.
    - "auto"   → sigue el esquema del sistema operativo.

Se llama al arranque (`app.main`) y cada vez que se cambia en Preferencias.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from transcriptor.config import Theme


def _dark_palette() -> QPalette:
    """Paleta oscura tipo editor (gris carbón con acento azul)."""
    p = QPalette()
    window = QColor(45, 45, 45)
    base = QColor(30, 30, 30)
    alt = QColor(53, 53, 53)
    text = QColor(220, 220, 220)
    disabled = QColor(127, 127, 127)
    highlight = QColor(38, 110, 183)

    p.setColor(QPalette.ColorRole.Window, window)
    p.setColor(QPalette.ColorRole.WindowText, text)
    p.setColor(QPalette.ColorRole.Base, base)
    p.setColor(QPalette.ColorRole.AlternateBase, alt)
    p.setColor(QPalette.ColorRole.ToolTipBase, window)
    p.setColor(QPalette.ColorRole.ToolTipText, text)
    p.setColor(QPalette.ColorRole.Text, text)
    p.setColor(QPalette.ColorRole.Button, alt)
    p.setColor(QPalette.ColorRole.ButtonText, text)
    p.setColor(QPalette.ColorRole.BrightText, QColor(255, 80, 80))
    p.setColor(QPalette.ColorRole.Link, highlight)
    p.setColor(QPalette.ColorRole.Highlight, highlight)
    p.setColor(QPalette.ColorRole.HighlightedText, Qt.GlobalColor.white)

    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        p.setColor(QPalette.ColorGroup.Disabled, role, disabled)
    return p


def _is_dark(app: QApplication, theme: Theme) -> bool:
    if theme == "oscuro":
        return True
    if theme == "claro":
        return False
    # "auto": seguir el SO (Qt 6.5+).
    return app.styleHints().colorScheme() == Qt.ColorScheme.Dark


def apply_theme(app: QApplication, theme: Theme) -> None:
    """Aplica el tema a la aplicación en marcha."""
    app.setStyle("Fusion")
    if _is_dark(app, theme):
        app.setPalette(_dark_palette())
    else:
        app.setPalette(app.style().standardPalette())
