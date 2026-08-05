"""Detección de plataforma y motor Whisper recomendado.

Devuelve uno de:
    "mlx"          → macOS Apple Silicon (arm64)
    "faster-cuda"  → GPU NVIDIA disponible (Windows/Linux)
    "faster-cpu"   → resto de casos
"""

from __future__ import annotations

import platform as _platform
import subprocess
import sys
from typing import Literal

Engine = Literal["mlx", "faster-cuda", "faster-cpu"]


def detect_os() -> str:
    """Devuelve un identificador legible del sistema operativo."""
    return _platform.system()  # "Darwin", "Windows", "Linux"


def is_apple_silicon() -> bool:
    """True si corremos en macOS sobre Apple Silicon (arm64)."""
    return sys.platform == "darwin" and _platform.machine() == "arm64"


def has_cuda() -> bool:
    """True si torch puede usar una GPU a través de su API `cuda`.

    OJO: esto incluye **AMD con ROCm**, que se presenta ante torch como `cuda`
    (ROCm traduce a HIP por debajo). Es la pregunta correcta para lo que corre
    sobre torch —diarización con pyannote, género con wav2vec2—, que así
    aprovecha una Radeon sin cambio alguno.

    NO es la pregunta correcta para elegir el motor de Whisper: ver `has_nvidia`.

    Si torch no está instalado (la UI arranca antes que el backend pesado),
    devuelve False sin romper.
    """
    try:
        # El ignore cubre los entornos sin torch (F0); unused-ignore evita el
        # warning donde torch sí está instalado.
        import torch  # type: ignore[import-not-found,unused-ignore]
    except ImportError:
        return False
    return bool(torch.cuda.is_available())


def has_rocm() -> bool:
    """True si la GPU que ve torch es AMD a través de ROCm."""
    try:
        import torch  # type: ignore[import-not-found,unused-ignore]
    except ImportError:
        return False
    return bool(getattr(torch.version, "hip", None)) and bool(torch.cuda.is_available())


def has_nvidia() -> bool:
    """True si hay una GPU NVIDIA con CUDA de verdad.

    Es la pregunta que debe hacerse **faster-whisper**: CTranslate2 se compila
    contra el CUDA de NVIDIA y no tiene backend ROCm/HIP, así que en una Radeon
    hay que transcribir en CPU aunque torch afirme que hay `cuda`. Sin esta
    distinción, en una máquina AMD con ROCm el motor pedía `device="cuda"` y
    CTranslate2 fallaba con "not compiled with CUDA support".

    Se distingue por `torch.version.cuda` / `torch.version.hip`: en una build
    ROCm el primero es None y el segundo trae la versión de HIP.
    """
    try:
        import torch  # type: ignore[import-not-found,unused-ignore]
    except ImportError:
        return False
    return bool(getattr(torch.version, "cuda", None)) and bool(torch.cuda.is_available())


def has_mps() -> bool:
    """True si torch puede usar la GPU integrada de Apple (Metal / MPS).

    Se usa para la diarización, que es la etapa más lenta del pipeline: medido
    en Apple Silicon, pyannote pasa de 233 s a 26 s (audio de 6:07) con
    resultados idénticos. No afecta a la transcripción, que en Mac va por MLX.

    Devuelve False si torch no está instalado (la UI arranca antes que el
    backend pesado) o si la build de torch no trae soporte MPS.
    """
    try:
        import torch  # type: ignore[import-not-found,unused-ignore]
    except ImportError:
        return False
    backend = getattr(torch.backends, "mps", None)
    return bool(backend is not None and backend.is_available())


def has_amd_gpu() -> bool:
    """True si el equipo tiene una GPU AMD/Radeon.

    No usa torch: se consulta al sistema, porque esto se pregunta desde la UI,
    que arranca antes que el backend pesado. Cualquier fallo de la consulta se
    interpreta como "no hay": es preferible no ofrecer el modo experimental que
    ofrecerlo donde no puede funcionar.
    """
    if sys.platform == "darwin":
        return False  # ROCm no existe en macOS
    if is_windows():
        try:
            salida = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name"],
                capture_output=True,
                text=True,
                timeout=15,
                creationflags=no_window_creationflags(),
            ).stdout
        except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
            return False
        return any(m in salida.lower() for m in ("amd", "radeon"))
    # Linux: el identificador de fabricante PCI de AMD es 0x1002.
    try:
        from pathlib import Path as _Path

        for vendor in _Path("/sys/class/drm").glob("card*/device/vendor"):
            if vendor.read_text().strip().lower() == "0x1002":
                return True
    except OSError:
        return False
    return False


def has_rocm_runtime() -> bool:
    """True si el runtime de ROCm está instalado y responde.

    `rocm-smi` viene con ROCm, así que su presencia es buena señal de que el
    stack completo está montado —que es justo la precondición del modo AMD—.
    """
    try:
        result = subprocess.run(
            ["rocm-smi"],
            capture_output=True,
            timeout=15,
            creationflags=no_window_creationflags(),
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def ctranslate2_supports_gpu() -> bool:
    """True si el CTranslate2 instalado se compiló con soporte de GPU.

    El paquete de PyPI viene sin él (o solo con CUDA de NVIDIA); el modo AMD
    exige el wheel ROCm de las releases de CTranslate2. Comprobarlo ANTES de
    transcribir evita que el usuario descubra el problema a mitad de un trabajo
    largo.
    """
    try:
        import ctranslate2  # type: ignore[import-not-found,unused-ignore]

        ctranslate2.get_supported_compute_types("cuda")
    except Exception:  # noqa: BLE001 — ausencia o build sin GPU: da igual cuál
        return False
    return True


def detect_engine() -> Engine:
    """Selecciona el motor Whisper óptimo para esta máquina.

    Usa `has_nvidia` y NO `has_cuda`: en una GPU AMD con ROCm, torch dice que
    hay `cuda` pero CTranslate2 no puede usarla, así que Whisper va a CPU. La
    Radeon sí se aprovecha en la diarización, que corre sobre torch.
    """
    if is_apple_silicon():
        return "mlx"
    if has_nvidia():
        return "faster-cuda"
    return "faster-cpu"


def engine_label(engine: Engine) -> str:
    """Etiqueta humana para mostrar en la UI."""
    return {
        "mlx": "MLX (Apple Silicon)",
        "faster-cuda": "faster-whisper (CUDA)",
        "faster-cpu": "faster-whisper (CPU)",
    }[engine]


def is_windows() -> bool:
    """True si corremos en Windows."""
    return sys.platform == "win32"


def no_window_creationflags() -> int:
    """`creationflags` para `subprocess` que oculta la consola en Windows.

    Devuelve 0 en macOS/Linux (no-op: 0 es el valor por defecto y válido en
    todas las plataformas). Evita usar `subprocess.CREATE_NO_WINDOW`
    directamente en código compartido, que solo existe en Windows.
    """
    if is_windows():
        import subprocess

        return subprocess.CREATE_NO_WINDOW
    return 0
