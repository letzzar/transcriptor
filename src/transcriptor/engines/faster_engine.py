"""Motor de transcripción basado en faster-whisper (CTranslate2).

Se usa en Windows, Linux y Mac Intel. En GPU NVIDIA corre en CUDA con
`float16`; si no hay GPU, cae a CPU con `int8`. El modelo se resuelve con
`models.registry.resolve(model_id)` (devuelve el repo CT2) y se descarga (o
reutiliza la caché) con `models.downloader.download(model_id)` antes de
construir el `WhisperModel`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from transcriptor.engines.base import Segment
from transcriptor.models import downloader
from transcriptor.platform_info import has_cuda


class FasterEngine:
    """Implementación de `TranscriptionEngine` para faster-whisper.

    `device` y `compute_type` aceptan `"auto"`: se resuelven en runtime según
    la presencia de GPU NVIDIA. Para forzar un valor concreto, pásalo en el
    constructor (p. ej. `device="cpu"`, `compute_type="int8"`).
    """

    def __init__(
        self,
        model_id: str = "large-v3-turbo",
        *,
        device: str = "auto",
        compute_type: str = "auto",
    ) -> None:
        self._model_id = model_id
        self._device = device
        self._compute_type = compute_type
        self._model_path: Path | None = None
        # WhisperModel cargado de forma diferida; tipado laxo porque
        # faster-whisper no expone stubs.
        self._model: object | None = None

    @property
    def model_id(self) -> str:
        return self._model_id

    def _resolve_device(self) -> str:
        if self._device != "auto":
            return self._device
        return "cuda" if has_cuda() else "cpu"

    def _resolve_compute_type(self, device: str) -> str:
        if self._compute_type != "auto":
            return self._compute_type
        return "float16" if device == "cuda" else "int8"

    def ensure_model(self) -> Path:
        """Descarga el modelo si no está y guarda la ruta local al snapshot."""
        if self._model_path is None:
            self._model_path = downloader.download(self._model_id)
        return self._model_path

    def _load_model(self) -> object:
        """Construye (una vez) el `WhisperModel` sobre el snapshot local."""
        if self._model is None:
            # Import diferido: faster-whisper no se instala en Mac Apple Silicon.
            from faster_whisper import WhisperModel

            model_path = self.ensure_model()
            device = self._resolve_device()
            compute_type = self._resolve_compute_type(device)
            self._model = WhisperModel(
                str(model_path),
                device=device,
                compute_type=compute_type,
            )
        return self._model

    def transcribe(
        self,
        audio: Path,
        *,
        language: str | None = None,
    ) -> Iterable[Segment]:
        model = self._load_model()

        kwargs: dict[str, object] = {}
        if language and language != "auto":
            kwargs["language"] = language

        # `transcribe` devuelve (generador_de_segmentos, info). El generador es
        # perezoso: materializamos a lista para devolver una secuencia estable.
        segments_iter, info = model.transcribe(str(audio), **kwargs)  # type: ignore[attr-defined]
        detected_lang = getattr(info, "language", None)

        return [
            Segment(
                text=str(seg.text).strip(),
                start=float(seg.start),
                end=float(seg.end),
                language=detected_lang,
            )
            for seg in segments_iter
        ]
