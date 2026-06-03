"""Informe de auditoría en texto plano (`*_ANALIZADO.txt` y resumen ejecutivo).

Mantiene el formato del prototipo para no romper la continuidad de auditorías
ya entregadas. Las funciones `render_*` son puras (devuelven str); las
`write_*` persisten a disco en UTF-8.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from pathlib import Path

from transcriptor.pipeline.hashing import FileMetadata
from transcriptor.pipeline.merge import LabeledSegment

ANALYSIS_SUFFIX = "_ANALIZADO.txt"
SUMMARY_FILENAME = "_RESUMEN_EJECUTIVO_AUDITORIA.txt"


@dataclass(frozen=True)
class SummaryEntry:
    """Una línea del resumen ejecutivo: un archivo procesado."""

    name: str
    language: str
    duration: str
    sha256: str


def format_timestamp(seconds: float) -> str:
    """Convierte segundos a "[MM:SS]"."""
    total = int(seconds)
    return f"[{total // 60:02d}:{total % 60:02d}]"


def render_analysis(
    *,
    source_name: str,
    language: str,
    enhanced: bool,
    metadata: FileMetadata,
    segments: list[LabeledSegment],
) -> str:
    """Genera el contenido de un `*_ANALIZADO.txt`."""
    lines = [
        f"Análisis de audio - {source_name}",
        f"Idioma: {language.upper()} | Limpieza: {'SÍ' if enhanced else 'NO'}",
        f"Duración: {metadata.duration} | sha256: {metadata.sha256}",
        "=" * 60 + "\n",
    ]
    for seg in segments:
        lines.append(f"{format_timestamp(seg.start)} ({seg.speaker}): {seg.text}")
    return "\n".join(lines)


def render_summary(entries: list[SummaryEntry], *, now: datetime.datetime | None = None) -> str:
    """Genera el contenido del resumen ejecutivo de la auditoría."""
    stamp = now or datetime.datetime.now()
    lines = [
        f"AUDITORÍA - {stamp}",
        f"Total de archivos procesados: {len(entries)}",
        "",
    ]
    for e in entries:
        lines.append(f"{e.name} | {e.language.upper()} | {e.duration} | sha256: {e.sha256}")
    return "\n".join(lines)


def write_analysis(folder: Path, source_name: str, content: str) -> Path:
    """Escribe el informe de un archivo en `folder` y devuelve su ruta."""
    out = folder / (Path(source_name).stem + ANALYSIS_SUFFIX)
    out.write_text(content, encoding="utf-8")
    return out


def write_summary(folder: Path, content: str) -> Path:
    """Escribe el resumen ejecutivo en `folder` y devuelve su ruta."""
    out = folder / SUMMARY_FILENAME
    out.write_text(content, encoding="utf-8")
    return out
