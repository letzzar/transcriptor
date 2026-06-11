"""Detección e instalación de FFmpeg.

La app necesita FFmpeg para convertir el audio a WAV. Si no está, ofrecemos
instalarlo automáticamente en Windows con winget (`Gyan.FFmpeg`); si el usuario
no quiere o winget falla, abrimos la web oficial para instalarlo a mano.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable

from transcriptor.platform_info import is_windows, no_window_creationflags

FFMPEG_URL = "https://www.ffmpeg.org/"
WINGET_ID = "Gyan.FFmpeg"

LineSink = Callable[[str], None]


def install_with_winget(on_line: LineSink | None = None) -> bool:
    """Instala FFmpeg con winget. Devuelve True si winget terminó con éxito.

    No interactivo: acepta los acuerdos de paquete y de fuente. Si winget no
    está disponible (no es Windows, o falta App Installer), devuelve False.
    """
    cmd = [
        "winget", "install", "-e", "--id", WINGET_ID,
        "--accept-package-agreements", "--accept-source-agreements",
    ]
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=no_window_creationflags(),
        )
    except (FileNotFoundError, OSError) as exc:
        if on_line is not None:
            on_line(f"No se pudo ejecutar winget: {exc}")
        return False

    assert proc.stdout is not None
    for line in proc.stdout:
        if on_line is not None:
            on_line(line.rstrip())
    return proc.wait() == 0


def refresh_path_from_registry() -> None:
    """Recarga `PATH` desde el registro (Windows) tras instalar.

    winget añade FFmpeg al PATH del usuario, pero el proceso en marcha no ve ese
    cambio. Releemos el PATH de máquina + usuario para detectar FFmpeg sin
    reiniciar la app.
    """
    if not is_windows():
        return
    import winreg

    parts: list[str] = []
    for root, sub in (
        (winreg.HKEY_LOCAL_MACHINE,
         r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
        (winreg.HKEY_CURRENT_USER, "Environment"),
    ):
        try:
            with winreg.OpenKey(root, sub) as key:
                value, _ = winreg.QueryValueEx(key, "Path")
        except OSError:
            continue
        parts.append(os.path.expandvars(str(value)))

    if parts:
        os.environ["PATH"] = os.pathsep.join([*parts, os.environ.get("PATH", "")])
