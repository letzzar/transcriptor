"""Motor de transcripción para Mac Apple Silicon basado en mlx-whisper.

Llama a `mlx_whisper.transcribe(path_or_hf_repo=...)`. El modelo se resuelve
con `models.registry.resolve(model_id)` y se descarga (o reutiliza la caché)
con `models.downloader.download(model_id)` antes de invocar el motor.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from transcriptor.engines.base import Segment
from transcriptor.models import downloader


class MlxEngine:
    """Implementación de `TranscriptionEngine` para mlx-whisper.

    Solo válido en macOS Apple Silicon. En otras plataformas, usar
    `FasterEngine` (F3).
    """

    def __init__(self, model_id: str = "large-v3-turbo") -> None:
        self._model_id = model_id
        self._model_path: Path | None = None

    @property
    def model_id(self) -> str:
        return self._model_id

    def ensure_model(self) -> Path:
        """Descarga el modelo si no está y guarda la ruta local."""
        if self._model_path is None:
            self._model_path = downloader.download(self._model_id)
        return self._model_path

    def transcribe(
        self,
        audio: Path,
        *,
        language: str | None = None,
    ) -> Iterable[Segment]:
        # Import diferido: mlx-whisper solo se instala en Mac Apple Silicon.
        import mlx_whisper

        model_path = self.ensure_model()

        kwargs: dict[str, object] = {"path_or_hf_repo": str(model_path)}
        if language and language != "auto":
            kwargs["language"] = language

        result = mlx_whisper.transcribe(str(audio), **kwargs)

        detected_lang = result.get("language") if isinstance(result, dict) else None
        segments_raw = result.get("segments", []) if isinstance(result, dict) else []

        return [
            Segment(
                text=str(seg.get("text", "")).strip(),
                start=float(seg.get("start", 0.0)),
                end=float(seg.get("end", 0.0)),
                language=detected_lang,
            )
            for seg in segments_raw
        ]
