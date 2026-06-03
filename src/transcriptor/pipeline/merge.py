"""Cruce de segmentos transcritos con turnos de diarización.

A cada `Segment` de Whisper le asigna el hablante con mayor solape temporal
entre los turnos de pyannote. Los hablantes se ordenan por tiempo total de
habla; solo los `max_speakers` principales reciben etiqueta "Voz N". El resto
se marca como interferencia, y los segmentos sin solape como voz desconocida.

NOTA: el prototipo (`app.py:255`) tenía el bug `max_ovl, speaker = spk`, que
desempaquetaba el string del hablante en lugar de actualizar el solape máximo.
Aquí se corrige (ver `_best_speaker`).
"""

from __future__ import annotations

from dataclasses import dataclass

from transcriptor.engines.base import Segment

UNKNOWN_SPEAKER = "Voz Desconocida"
MINOR_SPEAKER = "Interferencia / Voz menor"


@dataclass(frozen=True)
class Turn:
    """Tramo en que un hablante está activo, según la diarización."""

    speaker: str
    start: float
    end: float


@dataclass(frozen=True)
class LabeledSegment:
    """Segmento transcrito con su hablante ya resuelto para el informe."""

    start: float
    end: float
    text: str
    speaker: str  # "Voz 1", MINOR_SPEAKER o UNKNOWN_SPEAKER


def _speaker_durations(turns: list[Turn]) -> dict[str, float]:
    """Tiempo total de habla acumulado por hablante."""
    durations: dict[str, float] = {}
    for t in turns:
        durations[t.speaker] = durations.get(t.speaker, 0.0) + (t.end - t.start)
    return durations


def top_speakers(turns: list[Turn], max_speakers: int) -> list[str]:
    """Hablantes principales por tiempo de habla, hasta `max_speakers`."""
    ordered = sorted(_speaker_durations(turns).items(), key=lambda kv: kv[1], reverse=True)
    return [spk for spk, _ in ordered[:max_speakers]]


def _best_speaker(start: float, end: float, turns: list[Turn]) -> str | None:
    """Hablante con mayor solape con [start, end]; None si no hay solape.

    Corrige el bug del prototipo: actualiza `max_ovl` Y `speaker` juntos.
    """
    best: str | None = None
    max_ovl = 0.0
    for t in turns:
        ovl = min(end, t.end) - max(start, t.start)
        if ovl > max_ovl:
            max_ovl = ovl
            best = t.speaker
    return best


def assign_speakers(
    segments: list[Segment],
    turns: list[Turn],
    max_speakers: int,
) -> list[LabeledSegment]:
    """Etiqueta cada segmento con su hablante para el informe.

    - El hablante con más solape gana el segmento.
    - Solo los `max_speakers` con más tiempo de habla reciben "Voz N", numerados
      por orden de aparición en la transcripción.
    - Un hablante real pero fuera del top → `MINOR_SPEAKER`.
    - Sin solape con ningún turno → `UNKNOWN_SPEAKER`.
    """
    principals = top_speakers(turns, max_speakers)
    label_map: dict[str, str] = {}
    result: list[LabeledSegment] = []

    for seg in segments:
        best = _best_speaker(seg.start, seg.end, turns)
        if best is None:
            display = UNKNOWN_SPEAKER
        elif best in principals:
            if best not in label_map:
                label_map[best] = f"Voz {len(label_map) + 1}"
            display = label_map[best]
        else:
            display = MINOR_SPEAKER

        result.append(
            LabeledSegment(start=seg.start, end=seg.end, text=seg.text, speaker=display)
        )

    return result
