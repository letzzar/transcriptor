"""Tests del reparto de trabajo entre GPU NVIDIA, AMD (ROCm) y CPU.

ROCm hace que una GPU AMD se presente ante torch como `cuda`. Eso es una
ventaja para lo que corre sobre torch (diarización, género: aprovechan la
Radeon sin tocar nada) y una trampa para Whisper: CTranslate2 se compila contra
el CUDA de NVIDIA, no tiene backend HIP, y al pedirle `device="cuda"` aborta con
"This CTranslate2 package was not compiled with CUDA support".

De ahí que haya dos preguntas distintas: `has_cuda` (torch, incluye ROCm) y
`has_nvidia` (CTranslate2, solo NVIDIA de verdad).
"""

from __future__ import annotations

import pytest

from transcriptor import platform_info
from transcriptor.engines.faster_engine import FasterEngine


def _finge_gpu(
    monkeypatch: pytest.MonkeyPatch,
    *,
    cuda: str | None,
    hip: str | None,
    disponible: bool = True,
) -> None:
    """Simula la build de torch de una máquina concreta."""
    import torch

    monkeypatch.setattr(torch.version, "cuda", cuda, raising=False)
    monkeypatch.setattr(torch.version, "hip", hip, raising=False)
    monkeypatch.setattr(torch.cuda, "is_available", lambda: disponible)


def test_maquina_nvidia(monkeypatch: pytest.MonkeyPatch) -> None:
    _finge_gpu(monkeypatch, cuda="12.6", hip=None)
    assert platform_info.has_cuda() is True
    assert platform_info.has_nvidia() is True
    assert platform_info.has_rocm() is False


def test_maquina_amd_rocm(monkeypatch: pytest.MonkeyPatch) -> None:
    # Lo esencial: torch dice que hay `cuda`, pero NO es NVIDIA.
    _finge_gpu(monkeypatch, cuda=None, hip="6.1.40093")
    assert platform_info.has_cuda() is True
    assert platform_info.has_nvidia() is False
    assert platform_info.has_rocm() is True


def test_maquina_sin_gpu(monkeypatch: pytest.MonkeyPatch) -> None:
    _finge_gpu(monkeypatch, cuda="12.6", hip=None, disponible=False)
    assert platform_info.has_cuda() is False
    assert platform_info.has_nvidia() is False
    assert platform_info.has_rocm() is False


def test_whisper_no_pide_cuda_en_amd(monkeypatch: pytest.MonkeyPatch) -> None:
    # La regresión que se arregla: antes CTranslate2 recibía device="cuda" en
    # una Radeon y reventaba.
    _finge_gpu(monkeypatch, cuda=None, hip="6.1.40093")
    monkeypatch.setattr(platform_info, "is_apple_silicon", lambda: False)
    assert FasterEngine()._resolve_device() == "cpu"


def test_whisper_si_pide_cuda_en_nvidia(monkeypatch: pytest.MonkeyPatch) -> None:
    _finge_gpu(monkeypatch, cuda="12.6", hip=None)
    assert FasterEngine()._resolve_device() == "cuda"


def test_el_motor_detectado_en_amd_es_cpu(monkeypatch: pytest.MonkeyPatch) -> None:
    _finge_gpu(monkeypatch, cuda=None, hip="6.1.40093")
    monkeypatch.setattr(platform_info, "is_apple_silicon", lambda: False)
    assert platform_info.detect_engine() == "faster-cpu"


def test_la_diarizacion_si_usa_la_gpu_amd(monkeypatch: pytest.MonkeyPatch) -> None:
    # La otra mitad del arreglo: la Radeon NO se desperdicia. pyannote corre
    # sobre torch, así que ROCm la acelera igual que haría una NVIDIA.
    from transcriptor.pipeline import diarization

    _finge_gpu(monkeypatch, cuda=None, hip="6.1.40093")
    assert diarization.Diarizer()._resolve_device() == "cuda"
