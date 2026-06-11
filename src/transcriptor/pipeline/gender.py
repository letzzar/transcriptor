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

# Banda de frecuencia fundamental (F0) plausible para voz humana, en Hz.
_F0_MIN = 70.0
_F0_MAX = 300.0
# Se usa el percentil 25 del F0 (no la mediana): en audio telefónico la fundamental
# masculina (~120 Hz) está filtrada y la mediana sube engañosamente, pero los pocos
# tramos en que la voz grave aflora tiran del p25 hacia abajo; una voz femenina nunca
# baja tanto. Zonas "seguras" para corregir al modelo; en medio se respeta el modelo.
_F0_MALE_MAX = 175.0  # p25 por debajo → casi seguro hombre
_F0_FEMALE_MIN = 200.0  # p25 por encima → casi seguro mujer

# Etiqueta cuando ninguna señal es concluyente (preferible a un acierto dudoso
# en un peritaje legal).
INDETERMINATE = "indeterminado"
# Confianza mínima del modelo para fiarnos de él cuando el F0 no decide.
_MODEL_CONF_TRUST = 0.85


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


def estimate_f0(samples: np.ndarray, sample_rate: int) -> float | None:
    """Percentil 25 de la frecuencia fundamental (F0) de los tramos sonoros, en Hz.

    Método cepstral por ventanas (numpy, sin dependencias extra): el cepstrum
    detecta el ESPACIADO entre armónicos, que sobrevive aunque la fundamental
    esté ausente —el caso del audio telefónico (banda ~300-3400 Hz), donde la
    autocorrelación simple se engancha a un armónico y da un F0 demasiado alto—.

    Devuelve el percentil 25 (ver constantes _F0_*), no la mediana, y None si no
    hay suficientes tramos sonoros fiables. Se usa para corregir el sesgo del
    modelo (que tiende a clasificar voces masculinas telefónicas como "mujer").
    """
    import numpy as np

    frame = int(0.04 * sample_rate)  # ventanas de 40 ms
    hop = int(0.02 * sample_rate)  # salto de 20 ms
    if frame <= 0 or hop <= 0 or samples.size < frame:
        return None

    q_min = max(1, int(sample_rate / _F0_MAX))  # quefrencia = periodo en muestras
    q_max = int(sample_rate / _F0_MIN)
    if q_max <= q_min:
        return None

    # Posiciones de ventana, submuestreadas para acotar el coste a ~800 tramos.
    positions = range(0, samples.size - frame, hop)
    stride = max(1, len(positions) // 800)

    f0s: list[float] = []
    energies: list[float] = []
    segments: list[np.ndarray] = []
    for start in positions[::stride]:
        seg = samples[start : start + frame]
        segments.append(seg)
        energies.append(float(np.sqrt(np.mean(seg**2))))
    if not energies:
        return None
    e_max = max(energies)
    if e_max <= 0:
        return None

    window = np.hamming(frame)
    for seg, energy in zip(segments, energies):
        if energy < 0.15 * e_max:  # tramo en silencio/ruido → se ignora
            continue
        spec = np.fft.rfft(seg * window)
        cepstrum = np.fft.irfft(np.log(np.abs(spec) + 1e-10))
        q_window = cepstrum[q_min : q_max + 1]
        if q_window.size == 0:
            continue
        peak = float(q_window.max())
        # Voicing: el pico cepstral debe destacar sobre el ruido de la zona.
        if peak < q_window.mean() + 3.0 * q_window.std():
            continue
        q = int(q_window.argmax()) + q_min
        f0s.append(sample_rate / q)

    if len(f0s) < 5:
        return None
    return float(np.percentile(f0s, 25))


def _combine(label: str, conf: float, f0: float | None) -> tuple[str, float]:
    """Decide el género combinando el modelo y el pitch (F0).

    - F0 concluyente (≤175 Hz → hombre, ≥200 Hz → mujer): manda el F0, que es la
      señal sin sesgo; corrige al modelo si lo contradice.
    - F0 indeciso (ausente, o en la banda de solape 175–200 Hz): se fía del
      modelo solo si va confiado (≥0.85); si no, devuelve INDETERMINATE para no
      arriesgar una etiqueta dudosa en un peritaje legal.
    """
    if f0 is not None and f0 <= _F0_MALE_MAX:
        return "hombre", max(conf, 0.75)
    if f0 is not None and f0 >= _F0_FEMALE_MIN:
        return "mujer", max(conf, 0.75)
    # F0 no decide: solo el modelo, y únicamente si va seguro.
    if conf >= _MODEL_CONF_TRUST:
        return label, conf
    return INDETERMINATE, conf


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
        label, conf = classifier.classify(speaker_audio, sample_rate)
        f0 = estimate_f0(speaker_audio, sample_rate)
        result[speaker] = _combine(label, conf, f0)
    return result
