"""Interfaz común a todos los motores de transcripción.

Cada motor (mlx_engine, faster_engine) implementa el Protocol
`TranscriptionEngine` y devuelve una secuencia de `Segment`. La elección
del motor en runtime la hace `transcriptor.platform_info.detect_engine()`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol


@dataclass(frozen=True)
class Segment:
    """Un tramo de audio transcrito.

    Tiempos en segundos desde el inicio del archivo. `language` puede ser
    None si el motor no lo expone o todavía no se ha detectado.

    `avg_logprob` y `compression_ratio` son las métricas de calidad que Whisper
    calcula al decodificar (ambos motores las exponen igual). Las consume
    `merge.display_text` para marcar los tramos no fiables como ilegibles en vez
    de dar por buena una transcripción inventada. None si el motor no las da.
    """

    text: str
    start: float
    end: float
    language: str | None = None
    avg_logprob: float | None = None
    compression_ratio: float | None = None


class TranscriptionEngine(Protocol):
    """Contrato mínimo de un motor de transcripción."""

    def transcribe(
        self,
        audio: Path,
        *,
        language: str | None = None,
    ) -> Iterable[Segment]:
        """Transcribe `audio` y devuelve sus segmentos.

        Args:
            audio: ruta absoluta al archivo de audio.
            language: código ISO-639-1 (`es`, `en`, …) para forzar idioma.
                None → autodetección.
        """
        ...
