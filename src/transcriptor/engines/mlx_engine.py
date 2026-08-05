"""Motor de transcripción para Mac Apple Silicon basado en mlx-whisper.

Llama a `mlx_whisper.transcribe(path_or_hf_repo=...)`. El modelo se resuelve
con `models.registry.resolve(model_id)` y se descarga (o reutiliza la caché)
con `models.downloader.download(model_id)` antes de invocar el motor.

Idioma por ventana: Whisper decide el idioma UNA vez, con los primeros 30
segundos, y lo deja fijo para todo el archivo (incluido el tokenizador). En
grabaciones donde se mezclan idiomas eso arruina el resto: un audio de 36 min
detectado como catalán decodifica en catalán los 35 minutos de castellano que
vienen después. `mlx-whisper` no ofrece detección por ventana (faster-whisper
sí, con `multilingual=True`), así que se implementa aquí en dos fases:

    1. `_language_spans` recorre el mel en ventanas de 30 s -las nativas de
       Whisper- y detecta el idioma de cada una (solo encoder, barato).
    2. Se agrupan las ventanas consecutivas del mismo idioma y se transcribe
       cada grupo por separado, con SU idioma forzado.

Así solo se parte el audio donde el idioma cambia de verdad -que es justo
donde tiene sentido partirlo- y dentro de cada grupo Whisper conserva su
propia lógica de fin de frase.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from transcriptor.engines.base import Segment
from transcriptor.models import downloader

# Ventanas consecutivas que deben coincidir para aceptar un cambio de idioma.
#
# NO se filtra por confianza: medido sobre audio real, el detector se equivoca
# CON SEGURIDAD sobre el ruido (ventanas sueltas dando ru=0.925, pt=0.883,
# fi=0.803 en mitad de una conversación en castellano), así que un umbral de
# probabilidad no distingue el acierto del error. Lo que sí los distingue es la
# persistencia: una conversación no cambia de idioma durante 30 segundos para
# volver al anterior. Exigiendo 2 ventanas seguidas (60 s) caen las espurias y
# sobreviven los cambios reales. Esto arregla además el fallo original: el
# archivo entero se decodificaba en catalán por UNA ventana inicial suelta.
_LANGUAGE_HYSTERESIS = 2


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

        # Decodificación DETERMINISTA. Es un requisito de auditoría legal: el
        # mismo audio debe dar siempre la misma transcripción, o el informe no
        # se sostiene si la otra parte repite el análisis.
        #
        # `temperature=0.0` desactiva el reintento con muestreo aleatorio que
        # Whisper hace cuando una ventana falla sus umbrales de calidad.
        # `condition_on_previous_text=False` evita además que el texto ya
        # generado realimente las ventanas siguientes.
        #
        # Medido sobre un audio real (AUD-20260803-WA0000, 6:07), 3 procesos
        # independientes por configuración:
        #   por defecto     → 146 / 375 / 214 segmentos y 1 / 221 / 55 ilegibles
        #                     (tres transcripciones DISTINTAS del mismo archivo)
        #   esta config     → 84 segmentos y 3 ilegibles, huella idéntica las 3
        kwargs: dict[str, object] = {
            "path_or_hf_repo": str(model_path),
            "condition_on_previous_text": False,
            "temperature": 0.0,
        }
        # Idioma forzado por el usuario: un solo bloque, sin detección.
        if language and language != "auto":
            kwargs["language"] = language
            return self._transcribe_span(mlx_whisper, str(audio), kwargs, offset=0.0)

        from mlx_whisper.audio import SAMPLE_RATE, load_audio

        samples = load_audio(str(audio))
        segments: list[Segment] = []
        for start, end, lang in _language_spans(str(model_path), samples):
            span_kwargs = dict(kwargs, language=lang)
            segments.extend(
                self._transcribe_span(
                    mlx_whisper,
                    samples[start:end],
                    span_kwargs,
                    offset=start / SAMPLE_RATE,
                )
            )
        return segments

    def _transcribe_span(
        self,
        mlx_whisper: object,
        audio: object,
        kwargs: dict[str, object],
        *,
        offset: float,
    ) -> list[Segment]:
        """Transcribe un tramo y corrige sus tiempos al reloj del archivo."""
        result = mlx_whisper.transcribe(audio, **kwargs)  # type: ignore[attr-defined]
        if not isinstance(result, dict):
            return []
        detected_lang = result.get("language")
        return [
            Segment(
                text=str(seg.get("text", "")).strip(),
                start=float(seg.get("start", 0.0)) + offset,
                end=float(seg.get("end", 0.0)) + offset,
                language=detected_lang,
                avg_logprob=_opt_float(seg.get("avg_logprob")),
                compression_ratio=_opt_float(seg.get("compression_ratio")),
            )
            for seg in result.get("segments", [])
        ]


def _language_spans(model_path: str, samples: object) -> list[tuple[int, int, str]]:
    """Divide el audio en tramos homogéneos de idioma.

    Devuelve `(muestra_inicio, muestra_fin, idioma)` por tramo, ya fusionadas
    las ventanas consecutivas que comparten idioma. Si la detección falla,
    devuelve un único tramo con todo el audio y el idioma más probable.
    """
    from mlx_whisper.audio import N_FRAMES, N_SAMPLES, log_mel_spectrogram, pad_or_trim
    from mlx_whisper.decoding import detect_language
    from mlx_whisper.load_models import load_model

    model = load_model(model_path)
    mel = log_mel_spectrogram(samples, n_mels=model.dims.n_mels, padding=N_SAMPLES)
    content_frames = mel.shape[-2] - N_FRAMES

    crudos: list[str] = []
    for frame in range(0, max(content_frames, 1), N_FRAMES):
        window = pad_or_trim(mel[frame : frame + N_FRAMES], N_FRAMES, axis=-2)
        _, probs = detect_language(model, window.astype(mel.dtype))
        # Con un mel 2-D, detect_language desenvuelve y devuelve el dict suelto;
        # con uno 3-D devuelve una lista. Aceptamos las dos formas.
        if isinstance(probs, list):
            probs = probs[0]
        crudos.append(max(probs, key=probs.get))

    if not crudos:
        return [(0, len(samples), "es")]  # type: ignore[arg-type]

    idiomas = _apply_hysteresis(crudos)

    # Fusiona ventanas consecutivas del mismo idioma.
    spans: list[tuple[int, int, str]] = []
    inicio = 0
    for i in range(1, len(idiomas) + 1):
        if i == len(idiomas) or idiomas[i] != idiomas[inicio]:
            spans.append(
                (inicio * N_SAMPLES, min(i * N_SAMPLES, len(samples)), idiomas[inicio])  # type: ignore[arg-type]
            )
            inicio = i
    return spans


def _apply_hysteresis(crudos: list[str]) -> list[str]:
    """Descarta los cambios de idioma que no se sostienen.

    Un idioma sustituye al vigente solo si aparece en `_LANGUAGE_HYSTERESIS`
    ventanas seguidas. El idioma inicial es el primero que cumple esa condición
    (si ninguno la cumple, el de la primera ventana), de modo que una ventana
    inicial errónea no contamina el archivo entero.
    """
    vigente: str | None = None
    for i in range(len(crudos) - _LANGUAGE_HYSTERESIS + 1):
        tramo = crudos[i : i + _LANGUAGE_HYSTERESIS]
        if len(set(tramo)) == 1:
            vigente = tramo[0]
            break
    if vigente is None:
        return [crudos[0]] * len(crudos)

    salida: list[str] = []
    for i, crudo in enumerate(crudos):
        if crudo != vigente:
            siguientes = crudos[i : i + _LANGUAGE_HYSTERESIS]
            if len(siguientes) == _LANGUAGE_HYSTERESIS and len(set(siguientes)) == 1:
                vigente = crudo  # el cambio se sostiene: lo aceptamos
        salida.append(vigente)
    return salida


def _opt_float(value: object) -> float | None:
    """Convierte a float, o None si el motor no dio el dato."""
    return None if value is None else float(value)  # type: ignore[arg-type]
