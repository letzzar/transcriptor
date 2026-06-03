"""Acceso a los recursos empaquetados (iconos, fuentes)."""

from __future__ import annotations

from pathlib import Path

_RESOURCES = Path(__file__).resolve().parent.parent / "resources"


def app_icon_path() -> Path:
    """Ruta al icono de la aplicación (.ico)."""
    return _RESOURCES / "logo_app.ico"
