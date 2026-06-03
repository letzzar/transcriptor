"""Tests de `pipeline.merge.assign_speakers` (incluye la regresión del bug
`max_ovl, speaker = spk` del prototipo)."""

from __future__ import annotations

from transcriptor.engines.base import Segment
from transcriptor.pipeline.merge import (
    MINOR_SPEAKER,
    UNKNOWN_SPEAKER,
    LabeledSegment,
    Turn,
    assign_speakers,
    top_speakers,
)


def _seg(start: float, end: float, text: str = "x") -> Segment:
    return Segment(text=text, start=start, end=end)


def test_best_speaker_por_solape_maximo() -> None:
    # SPK_A solapa más con el segmento [0,10] que SPK_B.
    turns = [Turn("SPK_A", 0.0, 8.0), Turn("SPK_B", 8.0, 12.0)]
    out = assign_speakers([_seg(0.0, 10.0)], turns, max_speakers=2)
    assert out == [LabeledSegment(0.0, 10.0, "x", "Voz 1")]


def test_numeracion_por_orden_de_aparicion() -> None:
    # B habla más tiempo total, pero A aparece primero en la transcripción:
    # A debe ser "Voz 1" y B "Voz 2".
    turns = [Turn("A", 0.0, 2.0), Turn("B", 2.0, 20.0)]
    segments = [_seg(0.0, 1.9), _seg(3.0, 19.0)]
    out = assign_speakers(segments, turns, max_speakers=2)
    assert [s.speaker for s in out] == ["Voz 1", "Voz 2"]


def test_hablante_fuera_del_top_es_interferencia() -> None:
    turns = [
        Turn("A", 0.0, 30.0),
        Turn("B", 30.0, 50.0),
        Turn("C", 50.0, 52.0),  # poco tiempo → fuera del top-2
    ]
    seg = _seg(50.5, 51.5)  # solapa solo con C
    out = assign_speakers([seg], turns, max_speakers=2)
    assert out[0].speaker == MINOR_SPEAKER


def test_segmento_sin_solape_es_desconocido() -> None:
    turns = [Turn("A", 0.0, 5.0)]
    out = assign_speakers([_seg(100.0, 110.0)], turns, max_speakers=2)
    assert out[0].speaker == UNKNOWN_SPEAKER


def test_sin_turnos_todo_desconocido() -> None:
    out = assign_speakers([_seg(0.0, 10.0)], [], max_speakers=2)
    assert out[0].speaker == UNKNOWN_SPEAKER


def test_top_speakers_ordena_por_duracion() -> None:
    turns = [
        Turn("A", 0.0, 5.0),    # 5 s
        Turn("B", 5.0, 25.0),   # 20 s
        Turn("C", 25.0, 35.0),  # 10 s
    ]
    assert top_speakers(turns, 2) == ["B", "C"]
