"""Smoke test de la diarización (F4b).

Recibe la ruta de un audio POR ARGUMENTO (no se hardcodea ninguna ruta para no
filtrar material de auditoría). Convierte a WAV con `pipeline.audio`, ejecuta
`Diarizer.run()` y muestra SOLO metadatos (turnos, hablantes, tiempos). Nunca
imprime texto transcrito.

Uso:
    python tests/smoke_diarization.py "ruta\\al\\audio.m4a" [max_speakers]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from transcriptor.pipeline.audio import convert_to_wav
from transcriptor.pipeline.diarization import DiarizationError, Diarizer
from transcriptor.pipeline.merge import top_speakers


def main() -> int:
    if len(sys.argv) < 2:
        print("Uso: python tests/smoke_diarization.py <audio> [max_speakers]")
        return 2

    audio = Path(sys.argv[1])
    max_speakers = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    if not audio.exists():
        print(f"No existe el audio: {audio}")
        return 1

    print(f"Audio: {audio.name} ({audio.stat().st_size / 1024:.1f} KB)")
    print("Convirtiendo a WAV 16 kHz mono…")
    wav = convert_to_wav(audio)
    try:
        print("Cargando pyannote y diarizando (la 1ª vez descarga el modelo)…")
        t0 = time.perf_counter()
        diarizer = Diarizer()
        try:
            turns = diarizer.run(wav)
        except DiarizationError as e:
            print(f"\nFAIL (diarización): {e}")
            return 1
        elapsed = time.perf_counter() - t0
    finally:
        wav.unlink(missing_ok=True)

    speakers = {t.speaker for t in turns}
    principals = top_speakers(turns, max_speakers)
    total_speech = sum(t.end - t.start for t in turns)

    print(f"\n{len(turns)} turnos en {elapsed:.1f}s")
    print(f"Hablantes distintos: {len(speakers)} → {sorted(speakers)}")
    print(f"Principales (top {max_speakers}): {principals}")
    print(f"Habla total: {total_speech:.1f}s")
    print("(No se muestra texto transcrito — solo metadatos.)")

    if not turns:
        print("\nAVISO: 0 turnos (¿audio sin voz o muy corto?).")
        return 1

    print("\nOK — smoke test de diarización superado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
