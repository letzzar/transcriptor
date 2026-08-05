"""Tests de la elección de dispositivo para la diarización.

La diarización era el cuello de botella del pipeline en Mac (96% del tiempo)
porque `_resolve_device` solo miraba CUDA y en Apple Silicon caía siempre a
CPU. Medido: 233 s en CPU contra 26 s en MPS, con turnos idénticos.
"""

from __future__ import annotations

import pytest

from transcriptor.pipeline import diarization


@pytest.fixture
def sin_aceleradores(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diarization, "has_cuda", lambda: False)
    monkeypatch.setattr(diarization, "has_mps", lambda: False)


def test_cuda_tiene_prioridad(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diarization, "has_cuda", lambda: True)
    monkeypatch.setattr(diarization, "has_mps", lambda: True)
    assert diarization.Diarizer()._resolve_device() == "cuda"


def test_mps_cuando_no_hay_cuda(monkeypatch: pytest.MonkeyPatch) -> None:
    # El caso Mac: sin esto se perdía un 9x de rendimiento.
    monkeypatch.setattr(diarization, "has_cuda", lambda: False)
    monkeypatch.setattr(diarization, "has_mps", lambda: True)
    assert diarization.Diarizer()._resolve_device() == "mps"


def test_cpu_como_ultimo_recurso(sin_aceleradores: None) -> None:
    assert diarization.Diarizer()._resolve_device() == "cpu"


def test_device_explicito_manda(sin_aceleradores: None) -> None:
    # Poder forzar el dispositivo es lo que permitió comparar CPU contra MPS.
    assert diarization.Diarizer(device="cpu")._resolve_device() == "cpu"
    assert diarization.Diarizer(device="mps")._resolve_device() == "mps"
