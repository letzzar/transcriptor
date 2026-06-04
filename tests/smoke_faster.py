"""Smoke test del motor faster-whisper (F3).

Descarga el modelo `tiny` CT2 si falta y transcribe `tests/fixtures/jfk.flac`.
Aplica en Windows, Linux y Mac Intel (cualquier plataforma cuyo
`detect_engine()` no sea "mlx"). Sale con código 0 si ve segmentos no
vacíos, código 1 si algo falla, código 2 si la plataforma usa MLX.

Uso:
    .venv\\Scripts\\activate        (Windows)
    python tests/smoke_faster.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from transcriptor.engines.faster_engine import FasterEngine
from transcriptor.platform_info import detect_engine

# La consola de Windows usa cp1252 por defecto y no puede imprimir los
# caracteres Unicode de salida (flechas, ellipsis). Forzamos UTF-8.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

AUDIO = Path(__file__).parent / "fixtures" / "jfk.flac"


def main() -> int:
    if detect_engine() == "mlx":
        print(f"Motor activo: {detect_engine()} — usa smoke_mlx.py en Apple Silicon.")
        return 2

    if not AUDIO.exists():
        print(f"Falta el audio de prueba: {AUDIO}")
        return 1

    print(f"Audio: {AUDIO.name} ({AUDIO.stat().st_size / 1024:.1f} KB)")
    print(f"Motor: {detect_engine()}")
    print("Cargando FasterEngine(model='tiny')…")
    engine = FasterEngine(model_id="tiny")

    print("Descargando/leyendo modelo de caché HF…")
    t0 = time.perf_counter()
    model_path = engine.ensure_model()
    print(f"  ↳ modelo en {model_path} ({time.perf_counter() - t0:.1f}s)")

    print("Transcribiendo…")
    t0 = time.perf_counter()
    segments = list(engine.transcribe(AUDIO))
    elapsed = time.perf_counter() - t0

    print(f"\n{len(segments)} segmentos en {elapsed:.2f}s:")
    for s in segments:
        print(f"  [{s.start:6.2f} → {s.end:6.2f}] ({s.language}) {s.text}")

    if not segments:
        print("\nFAIL: lista de segmentos vacía.")
        return 1
    if not any(s.text for s in segments):
        print("\nFAIL: ningún segmento tiene texto.")
        return 1

    print("\nOK — smoke test del motor faster-whisper superado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
