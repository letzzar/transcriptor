"""Configuración persistente: ajustes normales en QSettings, secretos en keyring.

QSettings se localiza automáticamente:
    macOS    → ~/Library/Preferences/com.letzzar.Transcriptor.plist
    Windows  → HKCU\\Software\\letzzar\\Transcriptor

El HF_TOKEN nunca se escribe a disco en claro: vive en el keyring del SO
(Keychain en macOS, Credential Manager en Windows).

Toda la app debe pasar por estas funciones. No leer QSettings ni keyring
directamente desde widgets ni pipeline.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

import keyring
from PySide6.QtCore import QSettings

# Identificadores del servicio en el keyring
_KEYRING_SERVICE = "transcriptor"
_KEYRING_USER = "hf_token"

# Variable de entorno usada por el prototipo Tkinter. Solo se consulta como
# fallback de migración: si encontramos token en env y no en keyring, lo
# importamos al keyring y dejamos de mirar la env.
_LEGACY_ENV_VAR = "HF_TOKEN"

Theme = Literal["auto", "claro", "oscuro"]
Language = Literal["auto", "es", "en", "fr", "de", "it", "pt", "ca", "eu", "gl"]

_DEFAULT_THEME: Theme = "auto"
_DEFAULT_LANGUAGE: Language = "auto"


def _settings() -> QSettings:
    """Devuelve una instancia de QSettings. La identidad de organización y app
    se fija en `app.main()` antes de crear cualquier QSettings."""
    return QSettings()


# ---------------------------------------------------------------------------
# HF_TOKEN — secreto, vive en keyring
# ---------------------------------------------------------------------------

def get_hf_token() -> str | None:
    """Devuelve el token de HuggingFace, o None si no hay.

    Lookup:
        1. keyring del SO.
        2. Fallback: variable de entorno HF_TOKEN (migración del prototipo).
           Si la encuentra, la persiste en keyring y devuelve el valor.
    """
    token = keyring.get_password(_KEYRING_SERVICE, _KEYRING_USER)
    if token:
        return token

    legacy = os.getenv(_LEGACY_ENV_VAR, "").strip()
    if legacy:
        set_hf_token(legacy)
        return legacy

    return None


def set_hf_token(token: str) -> None:
    """Guarda el token en el keyring. Cadena vacía equivale a borrarlo."""
    token = token.strip()
    if not token:
        delete_hf_token()
        return
    keyring.set_password(_KEYRING_SERVICE, _KEYRING_USER, token)


def delete_hf_token() -> None:
    """Borra el token del keyring si existe (no falla si no estaba)."""
    try:
        keyring.delete_password(_KEYRING_SERVICE, _KEYRING_USER)
    except keyring.errors.PasswordDeleteError:
        pass


# ---------------------------------------------------------------------------
# Ruta de caché de modelos
# ---------------------------------------------------------------------------

def default_models_cache_dir() -> Path:
    """Caché de HuggingFace por defecto en el sistema del usuario."""
    return Path.home() / ".cache" / "huggingface" / "hub"


def get_models_cache_dir() -> Path:
    raw = _settings().value("models/cache_dir", "")
    if raw:
        return Path(str(raw)).expanduser()
    return default_models_cache_dir()


def set_models_cache_dir(path: Path | str | None) -> None:
    """Guarda la ruta. None o cadena vacía vuelve al default."""
    s = _settings()
    if path is None or str(path).strip() == "":
        s.remove("models/cache_dir")
    else:
        s.setValue("models/cache_dir", str(Path(path).expanduser()))


# ---------------------------------------------------------------------------
# Última carpeta de audios usada
# ---------------------------------------------------------------------------

def get_last_folder() -> Path | None:
    raw = _settings().value("ui/last_folder", "")
    if raw:
        p = Path(str(raw))
        if p.exists():
            return p
    return None


def set_last_folder(path: Path | str | None) -> None:
    s = _settings()
    if path is None:
        s.remove("ui/last_folder")
    else:
        s.setValue("ui/last_folder", str(Path(path)))


# ---------------------------------------------------------------------------
# Modelo preferido
# ---------------------------------------------------------------------------

def get_preferred_model() -> str | None:
    raw = _settings().value("models/preferred", "")
    return str(raw) if raw else None


def set_preferred_model(model_id: str | None) -> None:
    s = _settings()
    if model_id:
        s.setValue("models/preferred", model_id)
    else:
        s.remove("models/preferred")


# ---------------------------------------------------------------------------
# Tema
# ---------------------------------------------------------------------------

def get_theme() -> Theme:
    value = str(_settings().value("ui/theme", _DEFAULT_THEME))
    if value in ("auto", "claro", "oscuro"):
        return value  # type: ignore[return-value]
    return _DEFAULT_THEME


def set_theme(theme: Theme) -> None:
    _settings().setValue("ui/theme", theme)


# ---------------------------------------------------------------------------
# Idioma forzado para Whisper
# ---------------------------------------------------------------------------

def get_language() -> Language:
    value = str(_settings().value("transcribe/language", _DEFAULT_LANGUAGE))
    if value in ("auto", "es", "en", "fr", "de", "it", "pt", "ca", "eu", "gl"):
        return value  # type: ignore[return-value]
    return _DEFAULT_LANGUAGE


def set_language(language: Language) -> None:
    _settings().setValue("transcribe/language", language)
