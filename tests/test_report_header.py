"""Tests de la cabecera del informe y del etiquetado según el modo.

Regla del proyecto: el informe no puede insinuar análisis que no se han hecho.
Quien lo lea tiene que poder saber qué se buscó y qué no; si no, la ausencia de
interlocutores parecería que solo había una persona hablando.
"""

from __future__ import annotations

from transcriptor.pipeline.hashing import FileMetadata
from transcriptor.pipeline.merge import LabeledSegment
from transcriptor.report.txt import render_analysis
from transcriptor.workers.transcribe_worker import AnalysisMode

META = FileMetadata(sha256="abc123", duration="06:07", created="2026-08-05 10:00")


def _render(segments: list[LabeledSegment], analysis: str = "") -> str:
    return render_analysis(
        source_name="a.m4a",
        language="es",
        enhanced=False,
        metadata=META,
        segments=segments,
        analysis=analysis,
    )


def test_sin_hablante_no_se_inventa_etiqueta() -> None:
    # Modo "solo transcripción": no se ha diarizado, así que no hay "Voz 1".
    out = _render([LabeledSegment(0.0, 3.0, "Hola", "")])
    assert "[00:00] Hola" in out
    assert "Voz" not in out
    assert "()" not in out


def test_con_hablante_se_mantiene_el_formato_de_siempre() -> None:
    out = _render([LabeledSegment(0.0, 3.0, "Hola", "Voz 1")])
    assert "[00:00] (Voz 1): Hola" in out


def test_la_cabecera_dice_como_se_analizo() -> None:
    out = _render([], analysis=AnalysisMode.TRANSCRIPTION.report_description)
    assert "Análisis:" in out
    assert "NO se ha intentado identificar" in out


def test_sin_descripcion_la_cabecera_no_cambia() -> None:
    # Compatibilidad: los informes antiguos no llevaban esta línea.
    assert "Análisis:" not in _render([])


def test_cada_modo_declara_lo_que_no_hace() -> None:
    # Lo importante no es lo que se hizo, sino lo que NO: es lo que evita que el
    # lector saque conclusiones de más.
    for modo in AnalysisMode:
        descripcion = modo.report_description
        assert descripcion, modo
        if modo is not AnalysisMode.SPEAKERS_GENDER:
            assert "NO" in descripcion, modo


def test_el_modo_completo_no_necesita_advertencia() -> None:
    assert "NO" not in AnalysisMode.SPEAKERS_GENDER.report_description
