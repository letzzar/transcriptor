"""Conversión de audio a WAV 16 kHz mono con FFmpeg (y limpieza opcional).

Whisper y pyannote trabajan sobre WAV mono a 16 kHz. Este módulo localiza el
binario de FFmpeg y normaliza cualquier entrada a ese formato en un archivo
temporal que el llamador debe borrar al terminar.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from transcriptor.platform_info import is_windows, no_window_creationflags

# Filtros de reducción de ruido del prototipo (paso banda voz + denoise + gate).
# Cadena de limpieza. El orden importa:
#   highpass/lowpass → recorta fuera de la banda de voz telefónica.
#   afftdn           → reduce ruido de fondo.
#   dynaudnorm       → normaliza el nivel POR TRAMOS, que es lo que salva las
#                      grabaciones lejanas: sube la voz floja sin reventar los
#                      picos. Va después del denoise para no amplificar ruido.
#   agate            → puerta de ruido. El umbral es -45 dB y NO -30 dB: con
#                      -30 dB una grabación de nivel medio -32 dB (micrófono
#                      lejos, caso real) se quedaba prácticamente muda, porque
#                      la puerta cortaba la propia voz.
_CLEANUP_FILTERS = (
    "highpass=f=200, lowpass=f=3000, afftdn=nr=10:nf=-25, "
    "dynaudnorm=f=150:g=15:p=0.9, agate=threshold=-45dB:ratio=2"
)

# Extensiones de audio/vídeo que el pipeline acepta (FFmpeg las normaliza a WAV).
SUPPORTED_AUDIO_EXTENSIONS = frozenset(
    {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".opus", ".wma", ".mp4", ".aac"}
)


class FfmpegError(RuntimeError):
    """FFmpeg no está disponible o falló al convertir el audio."""


def find_ffmpeg() -> str | None:
    """Localiza FFmpeg: primero en el PATH, luego junto al ejecutable.

    Devuelve la ruta al binario o None si no se encuentra.
    """
    found = shutil.which("ffmpeg")
    if found:
        return found

    name = "ffmpeg.exe" if is_windows() else "ffmpeg"
    # Junto al ejecutable (FFmpeg empaquetado en el instalador offline) y en el cwd.
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).parent / name)
    candidates.append(Path.cwd() / name)
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def convert_to_wav(source: Path, *, enhance: bool = False) -> Path:
    """Convierte `source` a WAV 16 kHz mono en un archivo temporal.

    Args:
        source: ruta absoluta al audio original.
        enhance: si True, aplica filtros de reducción de ruido.

    Returns:
        Ruta al WAV temporal. El llamador es responsable de borrarlo.

    Raises:
        FfmpegError: si FFmpeg no se encuentra o la conversión falla.
    """
    ffmpeg = find_ffmpeg()
    if ffmpeg is None:
        raise FfmpegError(
            "No se encontró FFmpeg. Instálalo o colócalo junto a la aplicación."
        )

    fd, tmp_name = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    tmp = Path(tmp_name)

    command = [ffmpeg, "-y", "-i", str(source)]
    if enhance:
        command += ["-af", _CLEANUP_FILTERS]
    command += ["-ar", "16000", "-ac", "1", str(tmp)]

    try:
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=no_window_creationflags(),
        )
    except subprocess.CalledProcessError as exc:
        tmp.unlink(missing_ok=True)
        detail = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else str(exc)
        raise FfmpegError(f"FFmpeg falló al convertir {source.name}: {detail}") from exc

    return tmp
