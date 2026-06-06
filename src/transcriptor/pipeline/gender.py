"""Estimación de género por voz con un modelo wav2vec2 (transformers).

Es una ESTIMACIÓN, no un dato seguro: voces graves de mujer / agudas de hombre
y, sobre todo, el audio telefónico (banda limitada) la hacen falible. Por eso el
informe la etiqueta siempre como "probable …".

Funciona por hablante: se aíslan los tramos de cada voz (según la diarización),
se concatenan y se clasifican.
"""

from __future__ import annotations

import wave
from pathlib import Path
from typing import TYPE_CHECKING, Any

from transcriptor.pipeline.merge import Turn

if TYPE_CHECKING:
    import numpy as np

GENDER_MODEL = "alefiury/wav2vec2-large-xlsr-53-gender-recognition-librispeech"

# Etiquetas del modelo → español.
_LABEL_ES = {"male": "hombre", "female": "mujer"}

# Menos audio que esto para un hablante → no se estima (poco fiable).
_MIN_SECONDS = 1.0


class GenderClassifier:
    """Clasificador de género por voz (carga perezosa del modelo wav2vec2)."""

    def __init__(self, model: str = GENDER_MODEL) -> None:
        self._model_id = model
        self._feature_extractor: Any = None
        self._model: Any = None

    def _load(self) -> None:
        if self._model is None:
            # Import diferido: transformers es pesado.
            from transformers import (
                AutoFeatureExtractor,
                AutoModelForAudioClassification,
            )

            # transformers no tipa del todo `from_pretrained`.
            self._feature_extractor = AutoFeatureExtractor.from_pretrained(  # type: ignore[no-untyped-call]
                self._model_id
            )
            self._model = AutoModelForAudioClassification.from_pretrained(self._model_id)
            self._model.eval()

    def classify(self, samples: np.ndarray, sample_rate: int) -> tuple[str, float]:
        """Devuelve (etiqueta_es, confianza) para una señal mono float32."""
        import torch

        self._load()
        inputs = self._feature_extractor(
            samples, sampling_rate=sample_rate, return_tensors="pt"
        )
        with torch.no_grad():
            logits = self._model(**inputs).logits
        probs = torch.softmax(logits, dim=-1)[0]
        idx = int(probs.argmax())
        raw = str(self._model.config.id2label[idx])
        return _LABEL_ES.get(raw, raw), float(probs[idx])


def _load_samples(wav: Path) -> tuple[np.ndarray, int]:
    """Lee un WAV PCM 16-bit mono en float32 [-1, 1] y su sample rate."""
    import numpy as np

    with wave.open(str(wav), "rb") as w:
        sample_rate = w.getframerate()
        raw = w.readframes(w.getnframes())
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return samples, sample_rate


def classify_speakers(
    wav: Path,
    turns: list[Turn],
    classifier: GenderClassifier,
) -> dict[str, tuple[str, float]]:
    """Estima el género de cada hablante a partir de sus tramos de audio.

    Returns:
        {speaker_id: (etiqueta_es, confianza)}. Omite hablantes con menos de
        `_MIN_SECONDS` de audio acumulado.
    """
    import numpy as np

    samples, sample_rate = _load_samples(wav)

    spans: dict[str, list[tuple[float, float]]] = {}
    for turn in turns:
        spans.setdefault(turn.speaker, []).append((turn.start, turn.end))

    result: dict[str, tuple[str, float]] = {}
    for speaker, ranges in spans.items():
        slices = [
            samples[int(start * sample_rate) : int(end * sample_rate)]
            for start, end in ranges
        ]
        slices = [s for s in slices if s.size > 0]
        if not slices:
            continue
        speaker_audio = np.concatenate(slices)
        if speaker_audio.size < int(_MIN_SECONDS * sample_rate):
            continue
        result[speaker] = classifier.classify(speaker_audio, sample_rate)
    return result
