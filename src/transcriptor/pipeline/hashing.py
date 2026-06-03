"""Hash SHA-256 y metadatos del archivo de audio para la cadena de auditoría.

El hash se calcula sobre el archivo ORIGINAL (no el wav temporal), para que el
informe acredite el material de partida.
"""

from __future__ import annotations

import datetime
import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class FileMetadata:
    """Datos de auditoría de un archivo de audio."""

    sha256: str
    duration: str   # "MM:SS"
    created: str     # "YYYY-MM-DD HH:MM" o "Desconocida"


def sha256_file(path: Path, *, chunk_size: int = 65536) -> str:
    """Devuelve el SHA-256 hexadecimal del archivo leyéndolo por bloques."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def _duration_str(path: Path) -> str:
    """Duración "MM:SS" leída con tinytag; "00:00" si no se puede determinar."""
    try:
        from tinytag import TinyTag

        seconds = TinyTag.get(str(path)).duration
        if seconds is None:
            return "00:00"
        total = int(seconds)
        return f"{total // 60:02d}:{total % 60:02d}"
    except Exception:
        return "00:00"


def _created_str(path: Path) -> str:
    """Fecha de creación "YYYY-MM-DD HH:MM"; "Desconocida" si falla.

    Usa `st_birthtime` cuando existe (macOS); en su defecto `st_ctime`.
    """
    try:
        stat = path.stat()
        ts = getattr(stat, "st_birthtime", stat.st_ctime)
        return datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except OSError:
        return "Desconocida"


def file_metadata(path: Path) -> FileMetadata:
    """Calcula hash, duración y fecha de creación del archivo."""
    return FileMetadata(
        sha256=sha256_file(path),
        duration=_duration_str(path),
        created=_created_str(path),
    )
