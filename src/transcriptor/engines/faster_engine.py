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
from transcriptor.platform_info import ctranslate2_supports_gpu, has_nvidia


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
        amd_gpu: bool = False,
    ) -> None:
        self._model_id = model_id
        self._device = device
        self._compute_type = compute_type
        # Modo AMD experimental, activado por el usuario en la UI.
        self._amd_gpu = amd_gpu
        self._model_path: Path | None = None
        # WhisperModel cargado de forma diferida; tipado laxo porque
        # faster-whisper no expone stubs.
        self._model: object | None = None

    @property
    def model_id(self) -> str:
        return self._model_id

    def _resolve_device(self) -> str:
        """CUDA solo si es NVIDIA de verdad, o si el usuario activó el modo AMD.

        `has_nvidia` y no `has_cuda`: ROCm se presenta ante torch como `cuda`,
        pero el CTranslate2 de PyPI no tiene backend HIP y aborta con "not
        compiled with CUDA support". En una Radeon se transcribe en CPU y la GPU
        se aprovecha en la diarización, que sí corre sobre torch.

        EXCEPCIÓN: el modo AMD experimental. CTranslate2 fusionó soporte ROCm en
        feb-2026 y publica wheels (no en PyPI: van en las releases de GitHub).
        Con ese wheel instalado, el device sigue llamándose "cuda" y HIP lo
        traduce. Solo se activa si el usuario lo pide expresamente.
        """
        if self._device != "auto":
            return self._device
        if has_nvidia():
            return "cuda"
        if self._amd_gpu:
            return "cuda"  # el wheel ROCm expone HIP bajo el mismo nombre
        return "cpu"

    def _check_amd_ready(self) -> None:
        """Falla pronto y con un mensaje útil si el modo AMD no puede funcionar.

        Sin esto, el usuario descubriría el problema a mitad de un trabajo largo
        con un `ValueError` de CTranslate2 que no dice qué hacer.
        """
        if not ctranslate2_supports_gpu():
            raise RuntimeError(
                "El modo GPU AMD (experimental) está activado, pero el "
                "CTranslate2 instalado no trae soporte de GPU. Hace falta el "
                "wheel ROCm de las releases de CTranslate2 (no está en PyPI) y "
                "el runtime ROCm 7.1.1. Desactiva el modo para transcribir en CPU."
            )

    def _resolve_compute_type(self, device: str) -> str:
        if self._compute_type != "auto":
            return self._compute_type
        # En CUDA dejamos que CTranslate2 elija el tipo más rápido SOPORTADO por
        # la GPU ("auto"): float16 en Ampere+ (Tensor Cores), int8/float32 en
        # Pascal (1070 Ti), que no hace float16 eficiente y lo rechaza con error.
        return "auto" if device == "cuda" else "int8"

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

            if self._amd_gpu:
                self._check_amd_ready()
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

        # Mismo criterio que en MlxEngine (ver allí la justificación medida):
        # decodificación determinista, porque un informe pericial debe ser
        # reproducible. `temperature=0` desactiva el reintento aleatorio de
        # Whisper; sin esto faster-whisper usa la escalera 0.0→1.0 por defecto.
        # Ambos motores deben comportarse igual en las dos plataformas.
        kwargs: dict[str, object] = {
            "condition_on_previous_text": False,
            "temperature": 0.0,
        }
        if language and language != "auto":
            kwargs["language"] = language
        else:
            # Idioma por ventana (equivalente a `_language_spans` en MlxEngine):
            # sin esto, Whisper fija el idioma con los primeros 30 s y decodifica
            # el resto del archivo con él, aunque la conversación cambie de
            # idioma. faster-whisper lo trae de serie y sale casi gratis: reusa
            # la salida del encoder y solo cambia el token de idioma del prompt.
            kwargs["multilingual"] = True

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
                avg_logprob=float(seg.avg_logprob),
                compression_ratio=float(seg.compression_ratio),
            )
            for seg in segments_iter
        ]
