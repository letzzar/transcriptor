"""Tests de la provisión del backend para GPU AMD (variante `rocm`).

Sin esto, un cliente con Radeon recibía torch de CPU y el CTranslate2 de PyPI:
la GPU no se usaba en ninguna etapa, ni siquiera en la diarización, que sí
podría aprovecharla en Linux.

Las dos piezas NO están disponibles en las mismas plataformas:
  torch+ROCm  → solo Linux (PyTorch no publica wheels ROCm para Windows)
  CTranslate2 → Linux y Windows, pero fuera de PyPI
"""

from __future__ import annotations

import pytest

from transcriptor.runtime import provision


@pytest.fixture
def sin_red(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Captura los comandos de pip en vez de ejecutarlos."""
    ejecutados: list[list[str]] = []
    monkeypatch.setattr(provision, "_run", lambda cmd, on_line: ejecutados.append(cmd))
    monkeypatch.setattr(provision, "_venv_python", lambda: __import__("pathlib").Path("/fake/python"))
    monkeypatch.setattr(provision, "_marker_path", lambda: __import__("pathlib").Path("/dev/null"))
    monkeypatch.setattr(provision.Path, "exists", lambda self: True)
    monkeypatch.setattr(provision, "offline_wheelhouse", lambda: None)
    monkeypatch.setattr(provision, "is_apple_silicon", lambda: False)
    return ejecutados


def test_nvidia_tiene_prioridad_sobre_amd(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(provision, "detect_amd_gpu", lambda: True)
    # Con NVIDIA presente ni se pregunta por AMD: la variante es cu126.
    assert provision.CUDA_INDEX.endswith("cu126")


def test_amd_en_linux_usa_torch_rocm(
    sin_red: list[list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(provision, "detect_amd_gpu", lambda: True)
    monkeypatch.setattr(provision, "is_windows", lambda: False)
    monkeypatch.setattr(provision.sys, "platform", "linux")
    instalado: list[str] = []
    monkeypatch.setattr(
        provision, "_install_rocm_ctranslate2", lambda p, o: instalado.append("ct2")
    )

    assert provision.provision(gpu=False, python_exe="/fake/py") == "rocm"
    indices = [c[c.index("--index-url") + 1] for c in sin_red if "--index-url" in c]
    assert indices == [provision.ROCM_TORCH_INDEX]
    assert instalado == ["ct2"]


def test_amd_en_windows_deja_torch_en_cpu(
    sin_red: list[list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    # No existe torch+ROCm para Windows: torch se queda en CPU y solo se
    # sustituye CTranslate2. La diarización seguirá en CPU allí.
    monkeypatch.setattr(provision, "detect_amd_gpu", lambda: True)
    monkeypatch.setattr(provision, "is_windows", lambda: True)
    monkeypatch.setattr(provision.sys, "platform", "win32")
    instalado: list[str] = []
    monkeypatch.setattr(
        provision, "_install_rocm_ctranslate2", lambda p, o: instalado.append("ct2")
    )

    assert provision.provision(gpu=False, python_exe="/fake/py") == "rocm"
    indices = [c[c.index("--index-url") + 1] for c in sin_red if "--index-url" in c]
    assert indices == [provision.CPU_INDEX]
    assert instalado == ["ct2"]


def test_sin_amd_no_cambia_nada(
    sin_red: list[list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(provision, "detect_amd_gpu", lambda: False)
    monkeypatch.setattr(provision, "is_windows", lambda: True)
    monkeypatch.setattr(provision.sys, "platform", "win32")
    llamado: list[str] = []
    monkeypatch.setattr(
        provision, "_install_rocm_ctranslate2", lambda p, o: llamado.append("ct2")
    )

    assert provision.provision(gpu=False, python_exe="/fake/py") == "cpu"
    assert llamado == []


def test_el_esquema_subio_con_la_variante_nueva() -> None:
    # El marcador debe invalidarse en los backends ya provisionados, o un
    # cliente con Radeon se quedaría con el backend de CPU para siempre.
    assert provision._BACKEND_SCHEMA >= 4
