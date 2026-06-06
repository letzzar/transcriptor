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

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal

from transcriptor.engines import make_engine
from transcriptor.pipeline import audio, gender, hashing, merge
from transcriptor.pipeline.diarization import DiarizationError, Diarizer
from transcriptor.report import txt


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
        detect_gender: bool = False,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._folder = folder
        self._model_id = model_id
        self._max_speakers = max_speakers
        self._enhance = enhance
        self._language = language
        self._detect_gender = detect_gender

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
            diarizer = Diarizer()
            gender_clf = gender.GenderClassifier() if self._detect_gender else None
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
        diarizer: Diarizer,
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
            # Diarización (tolerante a fallos: cae a un solo hablante).
            self.status.emit("Identificando hablantes…")
            turns: list[merge.Turn] | None
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

            # Estimación de género (opcional) + asignación de hablantes.
            if turns is None:
                labeled = [
                    merge.LabeledSegment(s.start, s.end, s.text, "Voz 1") for s in segments
                ]
            else:
                genders: dict[str, str] | None = None
                if gender_clf is not None:
                    self.status.emit("Estimando género de las voces…")
                    raw = gender.classify_speakers(wav, turns, gender_clf)
                    genders = {spk: f"probable {label}" for spk, (label, _conf) in raw.items()}
                    if genders:
                        self.log.emit(
                            f"[{f.name}] Género estimado: "
                            + ", ".join(f"{s}={g}" for s, g in genders.items())
                        )
                labeled = merge.assign_speakers(segments, turns, self._max_speakers, genders)

            content = txt.render_analysis(
                source_name=f.name,
                language=language,
                enhanced=self._enhance,
                metadata=metadata,
                segments=labeled,
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
