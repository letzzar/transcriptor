"""Descarga e instalación del backend pesado en el primer arranque.

Estrategia (Opción C, "embed"): el ejecutable distribuido NO incluye torch ni
los motores (≈2 GB). La primera vez que se abre la app:

1. `detect_gpu()` mira si hay una GPU NVIDIA (vía `nvidia-smi`, sin necesitar
   torch todavía).
2. `provision()` crea un venv en una carpeta del usuario
   (`%LOCALAPPDATA%\\Transcriptor\\backend\\pyXY\\venv`) e instala con pip la
   variante adecuada: torch CUDA (`cu126`) o torch CPU, más faster-whisper,
   pyannote.audio y transformers (versiones fijadas). Usar un venv da semántica
   pip correcta: omite lo ya instalado y no re-descarga lo satisfecho.
3. `activate()` añade el `site-packages` del venv a `sys.path` (y, en Windows,
   las rutas de DLLs de NVIDIA/torch para que CTranslate2 encuentre
   cuDNN/cuBLAS en runtime).

El `python_exe` que crea el venv es parametrizable: en desarrollo es el del venv
actual (`sys.executable`); en el bundle, el Python embebido.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from transcriptor.platform_info import is_windows, no_window_creationflags

# Índices de wheels de PyTorch. cu126 trae torch 2.12 (lo probado) + las DLLs de
# cuDNN/cuBLAS (paquetes nvidia-*-cu12) que CTranslate2 necesita en GPU. OJO:
# pyannote.audio 4.0.4 exige torch>=2.8, así que el índice CUDA debe ser >= cu126
# (cu124 topa en torch 2.6 → ResolutionImpossible).
CUDA_INDEX = "https://download.pytorch.org/whl/cu126"
CPU_INDEX = "https://download.pytorch.org/whl/cpu"

# Paquetes pesados que NO van en el bundle y se instalan aquí, con versiones
# FIJADAS a lo probado: el cliente recibe EXACTAMENTE el stack validado. Sin pin
# pip instalaba el "latest" (p. ej. un pyannote.audio que rompía el import de
# Pipeline). Sus dependencias (ctranslate2, lightning…) las resuelve pip.
BACKEND_PACKAGES = (
    "faster-whisper==1.2.1",
    "pyannote.audio==4.0.4",
    "transformers==5.10.2",
)

# Versión del esquema de backend. Súbela al cambiar las versiones/layout de
# arriba: el marcador deja de coincidir y el siguiente arranque reinstala.
_BACKEND_SCHEMA = 3

_MARKER_NAME = ".provisioned"

# Callback opcional para enviar las líneas de salida de pip a la UI/consola.
LineSink = Callable[[str], None]


class ProvisionError(RuntimeError):
    """Falló la provisión del backend (descarga/instalación)."""


def _user_data_root() -> Path:
    """Carpeta de datos del usuario, sin permisos de admin, por plataforma."""
    if is_windows():
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "Transcriptor"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Transcriptor"
    return Path.home() / ".local" / "share" / "Transcriptor"


def backend_dir() -> Path:
    """Carpeta del backend, aislada por versión de Python.

    El sufijo `pyXY` evita mezclar wheels de ABIs distintas si el intérprete
    embebido cambia de versión en el futuro.
    """
    pyver = f"py{sys.version_info.major}{sys.version_info.minor}"
    return _user_data_root() / "backend" / pyver


def _venv_dir() -> Path:
    return backend_dir() / "venv"


def _venv_python() -> Path:
    if is_windows():
        return _venv_dir() / "Scripts" / "python.exe"
    return _venv_dir() / "bin" / "python"


def _site_packages() -> Path:
    if is_windows():
        return _venv_dir() / "Lib" / "site-packages"
    pyver = f"python{sys.version_info.major}.{sys.version_info.minor}"
    return _venv_dir() / "lib" / pyver / "site-packages"


def _marker_path() -> Path:
    return backend_dir() / _MARKER_NAME


def embedded_python_exe() -> str:
    """Intérprete que crea el venv del backend.

    En el bundle PyInstaller (`sys.frozen`) usa el Python embebido en
    `_internal/python/` (lo prepara `build_windows.bat`). En desarrollo (desde
    fuentes) usa el intérprete actual del venv.
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidate = Path(meipass) / "python" / "python.exe"
            if candidate.exists():
                return str(candidate)
    return sys.executable


def _bundle_dir() -> Path | None:
    """Carpeta de instalación (junto al exe) en el bundle, o None en desarrollo.

    `TRANSCRIPTOR_BUNDLE` permite simular el modo offline sin empaquetar.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    env = os.environ.get("TRANSCRIPTOR_BUNDLE")
    return Path(env) if env else None


def offline_wheelhouse() -> Path | None:
    """Wheelhouse offline (`wheels/`) junto al exe, o None (build online/dev)."""
    base = _bundle_dir()
    if base is not None and (base / "wheels").is_dir():
        return base / "wheels"
    return None


def offline_hf_cache() -> Path | None:
    """Caché de modelos HF empaquetada (`hf_cache/`) junto al exe, o None."""
    base = _bundle_dir()
    if base is not None and (base / "hf_cache").is_dir():
        return base / "hf_cache"
    return None


def is_offline_bundle() -> bool:
    """True si esta build trae los modelos HF empaquetados (instalador offline)."""
    return offline_hf_cache() is not None


def configure_offline() -> None:
    """Si hay modelos empaquetados, enruta HF a la caché local y corta la red.

    Idempotente. Debe llamarse MUY temprano (antes de importar transformers /
    huggingface_hub / pyannote). No-op en la build online o en desarrollo.
    """
    cache = offline_hf_cache()
    if cache is None:
        return
    os.environ.setdefault("HF_HOME", str(cache))
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"


def _read_marker() -> tuple[str, int] | None:
    """Lee el marcador como `(variante, esquema)`, o None si falta/no coincide.

    Devuelve None también para marcadores de un esquema anterior, de modo que
    `is_provisioned()` dé False y el backend se reinstale con el stack nuevo.
    """
    marker = _marker_path()
    if not marker.exists():
        return None
    lines = marker.read_text(encoding="utf-8").splitlines()
    if len(lines) < 2:
        return None  # marcador antiguo (solo variante) → reinstalar
    try:
        schema = int(lines[1].strip())
    except ValueError:
        return None
    if schema != _BACKEND_SCHEMA:
        return None
    return lines[0].strip(), schema


def is_provisioned() -> bool:
    """True si el backend instalado coincide con el esquema actual."""
    return _read_marker() is not None


def provisioned_variant() -> str | None:
    """Devuelve `"cu126"`/`"cpu"` si está provisionado al día, o None."""
    res = _read_marker()
    return res[0] if res else None


def detect_gpu() -> bool:
    """True si hay una GPU NVIDIA con driver (consulta `nvidia-smi`).

    No usa torch (que aún no está instalado en el primer arranque). Si
    `nvidia-smi` no existe o falla, asumimos que no hay GPU NVIDIA usable.
    """
    try:
        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            timeout=15,
            creationflags=no_window_creationflags(),
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _run(cmd: list[str], on_line: LineSink | None) -> None:
    """Lanza un comando en streaming, reenviando cada línea a `on_line`."""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=no_window_creationflags(),
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        if on_line is not None:
            on_line(line.rstrip())
    code = proc.wait()
    if code != 0:
        raise ProvisionError(f"comando salió con código {code}: {' '.join(cmd)}")


def provision(
    *,
    gpu: bool,
    python_exe: str | None = None,
    on_line: LineSink | None = None,
) -> str:
    """Instala el backend (torch + motores) en un venv de `backend_dir()`.

    `python_exe` por defecto es el Python embebido del bundle (o el del venv en
    desarrollo). Devuelve la variante instalada (`"cu126"` o `"cpu"`). Lanza
    `ProvisionError` si algún paso falla.
    """
    exe = python_exe or embedded_python_exe()
    variant = "cu126" if gpu else "cpu"
    torch_index = CUDA_INDEX if gpu else CPU_INDEX

    if not _venv_python().exists():
        # Instalación nueva o migración desde un layout anterior: partir limpio.
        if backend_dir().exists():
            shutil.rmtree(backend_dir(), ignore_errors=True)
        backend_dir().mkdir(parents=True, exist_ok=True)
        _run([exe, "-m", "venv", str(_venv_dir())], on_line)

    pip_base = [str(_venv_python()), "-m", "pip", "install", "--only-binary=:all:"]

    wheelhouse = offline_wheelhouse()
    if wheelhouse is not None:
        # Offline: todos los wheels (torch de la variante + motores + deps) están
        # empaquetados. Sin red: pip resuelve solo desde la carpeta local.
        _run(
            [*pip_base, "--no-index", "--find-links", str(wheelhouse / variant),
             "torch", *BACKEND_PACKAGES],
            on_line,
        )
    else:
        # Online: 1) torch desde el índice CUDA/CPU correcto (el venv lo registra);
        # 2) el resto desde PyPI, que ve torch ya instalado y lo respeta (satisface
        #    torch>=2.8 de pyannote sin re-descargarlo).
        _run([*pip_base, "--index-url", torch_index, "torch"], on_line)
        _run([*pip_base, *BACKEND_PACKAGES], on_line)

    _marker_path().write_text(f"{variant}\n{_BACKEND_SCHEMA}\n", encoding="utf-8")
    return variant


def activate() -> None:
    """Hace importable el backend: antepone su `site-packages` a `sys.path`.

    En Windows añade además las carpetas de DLLs de NVIDIA y de torch al buscador
    de DLLs, para que CTranslate2 (faster-whisper en CUDA) encuentre cuDNN/cuBLAS
    en runtime. Es idempotente y silenciosa si no hay backend.
    """
    sp = _site_packages()
    if not sp.is_dir():
        return
    if str(sp) not in sys.path:
        sys.path.insert(0, str(sp))
    if is_windows():
        _add_dll_dirs(sp)
    _add_embedded_stdlib()
    _install_venv_importer(sp)


def _install_venv_importer(site_packages: Path) -> None:
    """Da prioridad al venv del backend sobre los paquetes congelados del bundle.

    PyInstaller congela algunos paquetes que el backend también trae (tqdm,
    huggingface_hub…), pero PARCIALES (solo los submódulos que vio en nuestro
    código). Su importador tiene prioridad y ensombrece la copia COMPLETA del
    venv → fallan imports como `tqdm.contrib.logging`. Este finder, al frente de
    `sys.meta_path`, hace que cualquier paquete top-level presente en el venv se
    cargue desde ahí (completo); sus submódulos siguen el `__path__` del padre.
    Lo que NO está en el venv (PySide6, nuestro código) se sigue cargando del
    bundle. No-op fuera del bundle.
    """
    if not getattr(sys, "frozen", False):
        return
    import importlib.abc
    import importlib.machinery

    sp = str(site_packages)

    class _VenvFirstFinder(importlib.abc.MetaPathFinder):
        def find_spec(
            self,
            fullname: str,
            path: object = None,
            target: object = None,
        ) -> importlib.machinery.ModuleSpec | None:
            if path is not None:
                return None  # submódulos: los resuelve el __path__ del paquete padre
            return importlib.machinery.PathFinder.find_spec(fullname, [sp])

    if not any(type(f).__name__ == "_VenvFirstFinder" for f in sys.meta_path):
        sys.meta_path.insert(0, _VenvFirstFinder())


def _add_embedded_stdlib() -> None:
    """Añade la stdlib del Python embebido como fallback en `sys.path` (bundle).

    El bundle thin solo congela los módulos que importa NUESTRO código. El
    backend externo (torch, pyannote…) importa módulos stdlib extra (`cProfile`,
    `pstats`, `sqlite3`…) que PyInstaller no vio y no congeló. Los resolvemos
    desde la stdlib del Python embebido (mismo cp313), añadida AL FINAL del path
    para no pisar lo ya congelado. No-op fuera del bundle (en dev hay stdlib
    completa).
    """
    if not getattr(sys, "frozen", False):
        return
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        return
    py = Path(meipass) / "python"
    for sub in ("Lib", "DLLs"):
        path = py / sub
        if path.is_dir() and str(path) not in sys.path:
            sys.path.append(str(path))
    if is_windows():
        dlls = py / "DLLs"
        if dlls.is_dir():
            try:
                os.add_dll_directory(str(dlls))
            except OSError:
                pass


def _add_dll_dirs(site_packages: Path) -> None:
    """Registra las carpetas con DLLs nativas del backend (Windows)."""
    candidates = [site_packages / "torch" / "lib"]
    nvidia = site_packages / "nvidia"
    if nvidia.is_dir():
        candidates.extend(p / "bin" for p in nvidia.iterdir() if p.is_dir())
    for path in candidates:
        if path.is_dir():
            try:
                os.add_dll_directory(str(path))
            except OSError:
                # add_dll_directory puede fallar si la ruta desaparece; no es
                # fatal (otras rutas o el PATH pueden cubrir la DLL).
                pass


def _main() -> int:
    """CLI de prueba: provisiona desde el venv actual y verifica.

    Uso:  python -m transcriptor.runtime.provision [--cpu | --gpu]
    Sin flag, autodetecta la GPU. Pensado para validar en la máquina con GPU
    antes de tener el empaquetado.
    """
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "--cpu":
        gpu = False
    elif arg == "--gpu":
        gpu = True
    else:
        gpu = detect_gpu()

    print(f"GPU NVIDIA detectada: {gpu}")
    print(f"Backend en: {backend_dir()}")
    print(f"Variante a instalar: {'cu126 (CUDA)' if gpu else 'cpu'}")
    print("Instalando (esto descarga ~2 GB la primera vez)...\n")

    try:
        variant = provision(gpu=gpu, on_line=print)
    except ProvisionError as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1

    print(f"\nProvisión OK (variante {variant}). Verificando torch...")
    activate()
    import torch  # noqa: PLC0415  (verificación post-instalación)

    print(f"torch {torch.__version__}  cuda_disponible={torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
