"""Motores de transcripción y su selección en runtime.

`make_engine(model_id)` devuelve la implementación de `TranscriptionEngine`
adecuada para esta máquina según `platform.detect_engine()`:
    - "mlx"          → MlxEngine (Mac Apple Silicon)
    - "faster-cuda"  → FasterEngine en CUDA
    - "faster-cpu"   → FasterEngine en CPU

Los imports de cada motor son diferidos para no cargar mlx-whisper en
Windows ni faster-whisper en Mac ARM.
"""

from __future__ import annotations

from transcriptor.engines.base import Segment, TranscriptionEngine
from transcriptor.platform import detect_engine

__all__ = ["Segment", "TranscriptionEngine", "make_engine"]


def make_engine(model_id: str = "large-v3-turbo") -> TranscriptionEngine:
    """Crea el motor óptimo para esta plataforma."""
    if detect_engine() == "mlx":
        from transcriptor.engines.mlx_engine import MlxEngine

        return MlxEngine(model_id)

    from transcriptor.engines.faster_engine import FasterEngine

    return FasterEngine(model_id)
