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

# Texto con el que se sustituye un tramo que Whisper no transcribió con
# fiabilidad. En una auditoría legal es preferible dejar constancia de que ahí
# hay audio ininteligible antes que dar por buena una frase inventada.
ILLEGIBLE_TEXT = "[audio ilegible]"

# Umbrales de calidad de Whisper (sus propios valores por defecto al decodificar):
#   avg_logprob        → confianza media del tramo; por debajo, el modelo dudaba.
#   compression_ratio  → texto muy comprimible = repetitivo/degenerado, el
#                        clásico bucle de Whisper cuando el audio es ruido.
_MIN_AVG_LOGPROB = -1.0
_MAX_COMPRESSION_RATIO = 2.4


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


def display_text(segment: Segment) -> str:
    """Texto del segmento, o `ILLEGIBLE_TEXT` si Whisper no lo transcribió bien.

    Un motor que no exponga una métrica la deja a None; en ese caso no se juzga
    por ella (el texto se respeta si ninguna señal disponible lo desmiente).
    """
    if segment.avg_logprob is not None and segment.avg_logprob < _MIN_AVG_LOGPROB:
        return ILLEGIBLE_TEXT
    if (
        segment.compression_ratio is not None
        and segment.compression_ratio > _MAX_COMPRESSION_RATIO
    ):
        return ILLEGIBLE_TEXT
    return segment.text


def _speaker_durations(turns: list[Turn]) -> dict[str, float]:
    """Tiempo total de habla acumulado por hablante."""
    durations: dict[str, float] = {}
    for t in turns:
        durations[t.speaker] = durations.get(t.speaker, 0.0) + (t.end - t.start)
    return durations


def top_speakers(turns: list[Turn], max_speakers: int | None) -> list[str]:
    """Hablantes principales por tiempo de habla, hasta `max_speakers`.

    `max_speakers=None` → modo automático: devuelve TODOS los hablantes que la
    diarización detectó (sin tope), ordenados por tiempo de habla.
    """
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
    max_speakers: int | None,
    genders: dict[str, str] | None = None,
) -> list[LabeledSegment]:
    """Etiqueta cada segmento con su hablante para el informe.

    - El hablante con más solape gana el segmento.
    - `max_speakers=None` (automático): TODOS los hablantes detectados reciben
      "Voz N" (no hay tope ni "voz menor").
    - Con un entero: solo los `max_speakers` con más tiempo de habla reciben
      "Voz N" (numerados por orden de aparición); un hablante real fuera del top
      → `MINOR_SPEAKER`.
    - Sin solape con ningún turno → `UNKNOWN_SPEAKER`.
    - `genders` (opcional): {speaker_id: "probable mujer"} → se añade a la
      etiqueta, p. ej. "Voz 1 (probable mujer)".
    - El texto pasa por `display_text`: los tramos poco fiables se marcan como
      `ILLEGIBLE_TEXT`.
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
                label = f"Voz {len(label_map) + 1}"
                if genders and best in genders:
                    label += f" ({genders[best]})"
                label_map[best] = label
            display = label_map[best]
        else:
            display = MINOR_SPEAKER

        result.append(
            LabeledSegment(
                start=seg.start, end=seg.end, text=display_text(seg), speaker=display
            )
        )

    return result
