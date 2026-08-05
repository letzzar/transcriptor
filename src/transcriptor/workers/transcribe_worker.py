"""Worker que transcribe una carpeta de audios en segundo plano.

Orquesta el pipeline por archivo:
    audio.convert_to_wav → diarization.run → engine.transcribe
    → merge.assign_speakers → report.txt

Emite señales de progreso, log y estado para la UI. Nunca calcula en el hilo
de la UI. La cancelación se pide con `requestInterruption()` y se comprueba
entre archivos.

Criterio ante fallo de diarización (decisión del Director): no se pierde el
archivo; se transcribe igualmente etiquetando todo como "Voz 1" y se anota la
incidencia en el log.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from transcriptor.engines import make_engine
from transcriptor.engines.base import Segment
from transcriptor.pipeline import audio, gender, hashing, merge
from transcriptor.pipeline.diarization import DiarizationError, Diarizer
from transcriptor.report import txt


class AnalysisMode(StrEnum):
    """Nivel de análisis, ordenado de más rápido a más lento.

    Medido en Mac (Apple Silicon, large-v3-turbo, diarización en MPS) sobre un
    audio de 6:07, de punta a punta: 16,9 s / 32,5 s / 39,8 s / 48,4 s.

    Los cuatro escalones están mucho más juntos desde que la diarización corre
    en MPS: antes tardaba 241,9 s en CPU y era el 96% del trabajo; ahora son
    25,3 s. GENDER dejó de ser el atajo barato que era frente a SPEAKERS
    (32,5 s contra 39,8 s), pero mantiene su razón de ser: no necesita
    diarización, así que funciona sin token de HuggingFace.
    """

    TRANSCRIPTION = "transcription"
    GENDER = "gender"
    SPEAKERS = "speakers"
    SPEAKERS_GENDER = "speakers_gender"

    @property
    def needs_diarization(self) -> bool:
        return self in (AnalysisMode.SPEAKERS, AnalysisMode.SPEAKERS_GENDER)

    @property
    def needs_gender(self) -> bool:
        return self in (AnalysisMode.GENDER, AnalysisMode.SPEAKERS_GENDER)

    @property
    def report_description(self) -> str:
        """Qué se intentó identificar, para la cabecera del informe.

        Va en el informe porque quien lo lea (un juzgado, la otra parte) tiene
        que saber qué se analizó y qué NO: sin esto, la ausencia de hablantes
        podría interpretarse como que solo había una persona, cuando lo que
        pasa es que no se buscaron.
        """
        return {
            AnalysisMode.TRANSCRIPTION: (
                "Solo transcripción — NO se ha intentado identificar "
                "interlocutores ni estimar su sexo"
            ),
            AnalysisMode.GENDER: (
                "Transcripción + género — se ha estimado el sexo probable de cada "
                "intervención por separado; NO se han separado interlocutores, así "
                "que dos frases del mismo sexo pueden ser personas distintas"
            ),
            AnalysisMode.SPEAKERS: (
                "Transcripción + voces — se han separado los interlocutores; "
                "NO se ha estimado su sexo"
            ),
            AnalysisMode.SPEAKERS_GENDER: (
                "Transcripción + voces + género — se han separado los "
                "interlocutores y estimado el sexo probable de cada uno"
            ),
        }[self]


# Coste de cada modo como múltiplo de la duración del audio, medido de punta a
# punta en Mac (Apple Silicon, large-v3-turbo, diarización en MPS) sobre un
# audio real de 6:07. Sirve para avisar al usuario ANTES de lanzar un trabajo
# largo, no para prometer un tiempo exacto: en archivos cortos el coste fijo
# (cargar modelos) pesa más y la proporción sube.
MODE_COST: dict[AnalysisMode, float] = {
    AnalysisMode.TRANSCRIPTION: 0.05,
    AnalysisMode.GENDER: 0.09,
    AnalysisMode.SPEAKERS: 0.11,
    AnalysisMode.SPEAKERS_GENDER: 0.13,
}


class TranscribeWorker(QThread):
    """Transcribe todos los audios de una carpeta.

    Señales:
        status(str)        → etapa actual (para una etiqueta de estado).
        log(str)           → línea para el panel de logs.
        progress(int)      → porcentaje global 0-100 (por archivos).
        file_done(str)     → ruta del informe generado.
        failed(str)        → error fatal que aborta todo el trabajo.
        finished_ok(int)   → nº de archivos transcritos al terminar.
    """

    status = Signal(str)
    log = Signal(str)
    progress = Signal(int)
    file_done = Signal(str)
    failed = Signal(str)
    finished_ok = Signal(int)

    def __init__(
        self,
        folder: Path,
        *,
        model_id: str,
        max_speakers: int | None,
        enhance: bool,
        language: str | None,
        mode: AnalysisMode = AnalysisMode.SPEAKERS_GENDER,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._folder = folder
        self._model_id = model_id
        self._max_speakers = max_speakers
        self._enhance = enhance
        self._language = language
        self._mode = mode

    def _audio_files(self) -> list[Path]:
        return sorted(
            p
            for p in self._folder.iterdir()
            if p.is_file() and p.suffix.lower() in audio.SUPPORTED_AUDIO_EXTENSIONS
        )

    def run(self) -> None:
        try:
            files = self._audio_files()
            if not files:
                self.log.emit("No hay archivos de audio compatibles en la carpeta.")
                self.finished_ok.emit(0)
                return

            self.log.emit(f"{len(files)} archivo(s) a procesar con modelo '{self._model_id}'.")
            engine = make_engine(self._model_id)
            diarizer = Diarizer() if self._mode.needs_diarization else None
            gender_clf = gender.GenderClassifier() if self._mode.needs_gender else None
            entries: list[txt.SummaryEntry] = []
            total = len(files)

            for i, f in enumerate(files):
                if self.isInterruptionRequested():
                    self.log.emit("Cancelado por el usuario.")
                    break
                self._process_one(f, engine, diarizer, gender_clf, entries, first=(i == 0))
                self.progress.emit(int((i + 1) * 100 / total))

            if entries:
                txt.write_summary(self._folder, txt.render_summary(entries))
                self.log.emit(f"Resumen ejecutivo generado ({len(entries)} archivo(s)).")

            self.finished_ok.emit(len(entries))
        except Exception as e:  # noqa: BLE001 — error fatal, feedback a la UI
            self.failed.emit(str(e))

    def _process_one(
        self,
        f: Path,
        engine: object,
        diarizer: Diarizer | None,
        gender_clf: gender.GenderClassifier | None,
        entries: list[txt.SummaryEntry],
        *,
        first: bool,
    ) -> None:
        self.status.emit(f"Procesando {f.name}…")
        self.log.emit(f"[{f.name}] Calculando hash y metadatos…")
        try:
            metadata = hashing.file_metadata(f)
            wav = audio.convert_to_wav(f, enhance=self._enhance)
        except audio.FfmpegError as e:
            self.log.emit(f"[{f.name}] ERROR de audio: {e}")
            return

        try:
            # Diarización (solo en los modos que la piden; tolerante a fallos).
            turns: list[merge.Turn] | None = None
            if diarizer is not None:
                self.status.emit("Identificando hablantes…")
                try:
                    turns = diarizer.run(wav)
                    speakers = len({t.speaker for t in turns})
                    self.log.emit(f"[{f.name}] {len(turns)} turnos, {speakers} hablante(s).")
                except DiarizationError as e:
                    turns = None
                    self.log.emit(f"[{f.name}] AVISO: diarización no disponible ({e}). "
                                  "Se transcribe con un solo hablante.")

            # Transcripción.
            if first:
                self.status.emit("Cargando motor de transcripción (puede tardar la 1ª vez)…")
            else:
                self.status.emit("Transcribiendo…")
            segments = list(engine.transcribe(wav, language=self._language))  # type: ignore[attr-defined]
            language = segments[0].language if segments and segments[0].language else "?"

            # Etiquetado, según el modo.
            if turns is None and gender_clf is not None:
                # Modo "transcripción + género": sin diarización no hay hablantes
                # que agrupar, así que se estima el género de CADA frase por
                # separado. No se afirma que dos frases del mismo género sean la
                # misma persona: solo se describe lo que suena en cada tramo.
                labeled = self._label_by_gender(f, wav, segments, gender_clf)
            elif turns is None:
                # Sin diarización no sabemos cuántas personas hablan: la etiqueta
                # se deja VACÍA. Poner "Voz 1" afirmaría una identificación que
                # no se ha hecho (y sugeriría que solo hay un interlocutor).
                labeled = [
                    merge.LabeledSegment(s.start, s.end, merge.display_text(s), "")
                    for s in segments
                ]
            else:
                genders: dict[str, str] | None = None
                if gender_clf is not None:
                    try:
                        self.status.emit("Estimando género de las voces…")
                        # El género se estima SIEMPRE sobre audio sin filtrar: el
                        # filtro de mejora (highpass=200) borra la fundamental de
                        # la voz masculina (~85-180 Hz) y sesga a "mujer".
                        gender_wav = (
                            wav if not self._enhance
                            else audio.convert_to_wav(f, enhance=False)
                        )
                        try:
                            raw = gender.classify_speakers(gender_wav, turns, gender_clf)
                        finally:
                            if gender_wav != wav:
                                gender_wav.unlink(missing_ok=True)
                        genders = {
                            spk: (
                                "género indeterminado"
                                if label == gender.INDETERMINATE
                                else f"probable {label}"
                            )
                            for spk, (label, _conf) in raw.items()
                        }
                        if genders:
                            self.log.emit(
                                f"[{f.name}] Género estimado: "
                                + ", ".join(f"{s}={g}" for s, g in genders.items())
                            )
                    except Exception as e:  # noqa: BLE001 — el género es opcional
                        genders = None
                        self.log.emit(
                            f"[{f.name}] AVISO: estimación de género no disponible "
                            f"({type(e).__name__}: {e})."
                        )
                labeled = merge.assign_speakers(segments, turns, self._max_speakers, genders)

            content = txt.render_analysis(
                source_name=f.name,
                language=language,
                enhanced=self._enhance,
                metadata=metadata,
                segments=labeled,
                analysis=self._describe_analysis(turns is not None),
            )
            out = txt.write_analysis(self._folder, f.name, content)
            entries.append(
                txt.SummaryEntry(
                    name=f.name,
                    language=language,
                    duration=metadata.duration,
                    sha256=metadata.sha256,
                )
            )
            self.log.emit(f"[{f.name}] Generado {out.name} ({len(labeled)} segmentos).")
            self.file_done.emit(str(out))
        except Exception as e:  # noqa: BLE001 — error de un archivo; seguimos con el resto
            import traceback

            self.log.emit(
                f"[{f.name}] ERROR: {type(e).__name__}: {e}\n{traceback.format_exc()}"
            )
        finally:
            wav.unlink(missing_ok=True)

    def _describe_analysis(self, diarizado: bool) -> str:
        """Descripción para la cabecera, corregida por lo que REALMENTE pasó.

        Si se pidió separar interlocutores y la diarización falló (sin token,
        sin red…), la cabecera no puede seguir afirmando que se separaron.
        """
        descripcion = self._mode.report_description
        if self._mode.needs_diarization and not diarizado:
            return (
                "Transcripción — se intentó separar los interlocutores y NO fue "
                "posible, así que el texto va sin identificar"
            )
        return descripcion

    def _label_by_gender(
        self,
        f: Path,
        wav: Path,
        segments: list[Segment],
        gender_clf: gender.GenderClassifier,
    ) -> list[merge.LabeledSegment]:
        """Etiqueta cada frase con su género estimado, sin diarización."""
        try:
            self.status.emit("Estimando género de cada frase…")
            gender_wav = wav if not self._enhance else audio.convert_to_wav(f, enhance=False)
            try:
                etiquetas = gender.classify_ranges(
                    gender_wav, [(s.start, s.end) for s in segments], gender_clf
                )
            finally:
                if gender_wav != wav:
                    gender_wav.unlink(missing_ok=True)
        except Exception as e:  # noqa: BLE001 — el género es opcional
            self.log.emit(
                f"[{f.name}] AVISO: estimación de género no disponible "
                f"({type(e).__name__}: {e})."
            )
            etiquetas = [None] * len(segments)

        return [
            merge.LabeledSegment(
                s.start,
                s.end,
                merge.display_text(s),
                _gender_label(etiqueta),
            )
            for s, etiqueta in zip(segments, etiquetas)
        ]


def _gender_label(etiqueta: str | None) -> str:
    """Texto del hablante para el modo por frase.

    Nunca dice "Voz N": sin diarización no sabemos si dos frases son la misma
    persona, y en un peritaje no se afirma lo que no se ha medido.
    """
    if etiqueta is None:
        return "voz no estimable"
    if etiqueta == gender.INDETERMINATE:
        return "género indeterminado"
    return f"probable {etiqueta}"
