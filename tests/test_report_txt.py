"""Tests del renderizado de informes de texto."""

from __future__ import annotations

import datetime

from transcriptor.pipeline.hashing import FileMetadata
from transcriptor.pipeline.merge import LabeledSegment
from transcriptor.report.txt import (
    SummaryEntry,
    format_timestamp,
    render_analysis,
    render_summary,
)


def test_format_timestamp() -> None:
    assert format_timestamp(0) == "[00:00]"
    assert format_timestamp(65.4) == "[01:05]"
    assert format_timestamp(3599) == "[59:59]"


def test_render_analysis_cabecera_y_lineas() -> None:
    meta = FileMetadata(sha256="abc123", duration="01:30", created="2026-06-03 10:00")
    segments = [
        LabeledSegment(0.0, 5.0, "Hola qué tal", "Voz 1"),
        LabeledSegment(5.0, 9.0, "Muy bien", "Voz 2"),
    ]
    out = render_analysis(
        source_name="audio.m4a",
        language="es",
        enhanced=True,
        metadata=meta,
        segments=segments,
    )
    assert "Análisis de audio - audio.m4a" in out
    assert "Idioma: ES | Limpieza: SÍ" in out
    assert "sha256: abc123" in out
    assert "[00:00] (Voz 1): Hola qué tal" in out
    assert "[00:05] (Voz 2): Muy bien" in out


def test_render_summary() -> None:
    entries = [
        SummaryEntry(name="a.mp3", language="es", duration="00:30", sha256="aaa"),
        SummaryEntry(name="b.wav", language="en", duration="01:00", sha256="bbb"),
    ]
    now = datetime.datetime(2026, 6, 3, 12, 0, 0)
    out = render_summary(entries, now=now)
    assert "Total de archivos procesados: 2" in out
    assert "a.mp3 | ES | 00:30 | sha256: aaa" in out
    assert "b.wav | EN | 01:00 | sha256: bbb" in out
