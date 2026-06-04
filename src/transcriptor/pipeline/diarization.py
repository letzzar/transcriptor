"""Diarización de hablantes con pyannote.audio 4.x.

Envuelve el `Pipeline` de pyannote y devuelve los turnos como `list[Turn]`
(la estructura que consume `merge.assign_speakers`), de modo que el resto del
pipeline no depende de los tipos de pyannote.

Decodificación de audio: pyannote 4.x usa `torchcodec`, que en Windows exige
las DLLs "full-shared" de FFmpeg. Para evitar esa dependencia frágil, se le
pasa el audio ya decodificado en memoria (`{"waveform", "sample_rate"}`). El
WAV de entrada lo produce `pipeline.audio.convert_to_wav` (16 kHz mono 16-bit),
así que basta leerlo con el módulo `wave` de la stdlib.

Requiere un HF_TOKEN válido (keyring) y haber aceptado las condiciones del
modelo `pyannote/speaker-diarization-community-1` en HuggingFace (el modelo
insignia de pyannote 4.x; la 4.x lo usa internamente aunque se pida la "3.1").
"""

from __future__ import annotations

import wave
from pathlib import Path
from typing import TYPE_CHECKING, Any

from transcriptor import config
from transcriptor.pipeline.merge import Turn
from transcriptor.platform_info import has_cuda

if TYPE_CHECKING:
    import torch

DEFAULT_MODEL = "pyannote/speaker-diarization-community-1"


class DiarizationError(RuntimeError):
    """No se pudo cargar o ejecutar la diarización."""


def _load_waveform(wav: Path) -> tuple[torch.Tensor, int]:
    """Lee un WAV PCM en un tensor float32 (channel, time) normalizado [-1, 1]."""
    import numpy as np
    import torch

    with wave.open(str(wav), "rb") as w:
        sample_rate = w.getframerate()
        n_channels = w.getnchannels()
        frames = w.readframes(w.getnframes())

    data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if n_channels > 1:
        data = data.reshape(-1, n_channels).T  # (channel, time)
    else:
        data = data.reshape(1, -1)
    return torch.from_numpy(data.copy()), sample_rate


class Diarizer:
    """Carga perezosa del pipeline de pyannote y diarización por archivo."""

    def __init__(self, model: str = DEFAULT_MODEL, *, device: str = "auto") -> None:
        self._model = model
        self._device = device
        # pyannote no expone stubs: tipamos el pipeline como Any.
        self._pipeline: Any | None = None

    def _resolve_device(self) -> str:
        if self._device != "auto":
            return self._device
        return "cuda" if has_cuda() else "cpu"

    def load(self) -> Any:
        """Construye (una vez) el pipeline de pyannote sobre el device elegido."""
        if self._pipeline is not None:
            return self._pipeline

        # Imports diferidos: torch y pyannote son pesados (~2 GB).
        import torch
        from pyannote.audio import Pipeline

        token = config.get_hf_token()
        if not token:
            raise DiarizationError(
                "Falta el token de HuggingFace. Configúralo en Preferencias para "
                "poder identificar los hablantes."
            )

        pipeline = Pipeline.from_pretrained(self._model, token=token)
        if pipeline is None:
            raise DiarizationError(
                f"No se pudo cargar '{self._model}'. Acepta las condiciones del "
                "modelo en huggingface.co y verifica que tu token tiene acceso."
            )

        pipeline.to(torch.device(self._resolve_device()))
        self._pipeline = pipeline
        return pipeline

    def run(self, wav: Path) -> list[Turn]:
        """Diariza un WAV y devuelve sus turnos ordenados por aparición."""
        pipeline = self.load()
        waveform, sample_rate = _load_waveform(wav)
        output = pipeline({"waveform": waveform, "sample_rate": sample_rate})
        # pyannote 4.x devuelve un `DiarizeOutput` con `.speaker_diarization`
        # (Annotation); versiones legacy devuelven el Annotation directamente.
        annotation = getattr(output, "speaker_diarization", output)
        return [
            Turn(speaker=speaker, start=float(segment.start), end=float(segment.end))
            for segment, _, speaker in annotation.itertracks(yield_label=True)
        ]
