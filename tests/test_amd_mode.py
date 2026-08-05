"""Tests del modo EXPERIMENTAL de transcripción en GPU AMD (ROCm).

CTranslate2 fusionó soporte ROCm/HIP en feb-2026 (PR #1989) y publica wheels
para Linux y Windows en sus releases —no en PyPI—. El modo existe para poder
probarlo en una máquina con Radeon, pero va apagado por defecto: su propio autor
advierte de que RDNA2 (las RX 6000) está sin verificar.

Lo que estos tests protegen sobre todo es que, **apagado, no cambie nada**.
"""

from __future__ import annotations

import pytest

from transcriptor import platform_info
from transcriptor.engines.faster_engine import FasterEngine


@pytest.fixture
def sin_nvidia(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(platform_info, "has_nvidia", lambda: False)
    import transcriptor.engines.faster_engine as fe

    monkeypatch.setattr(fe, "has_nvidia", lambda: False)


def test_apagado_transcribe_en_cpu(sin_nvidia: None) -> None:
    # El comportamiento por defecto en una Radeon: CPU, como hasta ahora.
    assert FasterEngine()._resolve_device() == "cpu"


def test_encendido_pide_gpu(sin_nvidia: None) -> None:
    assert FasterEngine(amd_gpu=True)._resolve_device() == "cuda"


def test_nvidia_no_depende_del_modo(monkeypatch: pytest.MonkeyPatch) -> None:
    # En NVIDIA el modo AMD es irrelevante: se usa CUDA de todos modos.
    import transcriptor.engines.faster_engine as fe

    monkeypatch.setattr(fe, "has_nvidia", lambda: True)
    assert FasterEngine()._resolve_device() == "cuda"
    assert FasterEngine(amd_gpu=True)._resolve_device() == "cuda"


def test_device_explicito_sigue_mandando(sin_nvidia: None) -> None:
    assert FasterEngine(device="cpu", amd_gpu=True)._resolve_device() == "cpu"


def test_avisa_pronto_si_falta_el_wheel_rocm(monkeypatch: pytest.MonkeyPatch) -> None:
    # Sin el CTranslate2 con GPU, el usuario debe enterarse ANTES de empezar un
    # trabajo largo, y con un mensaje que diga qué hacer.
    import transcriptor.engines.faster_engine as fe

    monkeypatch.setattr(fe, "ctranslate2_supports_gpu", lambda: False)
    with pytest.raises(RuntimeError, match="ROCm"):
        FasterEngine(amd_gpu=True)._check_amd_ready()


def test_no_avisa_si_el_wheel_esta(monkeypatch: pytest.MonkeyPatch) -> None:
    import transcriptor.engines.faster_engine as fe

    monkeypatch.setattr(fe, "ctranslate2_supports_gpu", lambda: True)
    FasterEngine(amd_gpu=True)._check_amd_ready()  # no lanza


def test_en_macos_no_se_ofrece_amd(monkeypatch: pytest.MonkeyPatch) -> None:
    # ROCm no existe en macOS: el interruptor no debe aparecer siquiera.
    monkeypatch.setattr(platform_info.sys, "platform", "darwin")
    assert platform_info.has_amd_gpu() is False


def test_make_engine_propaga_la_opcion(monkeypatch: pytest.MonkeyPatch) -> None:
    from transcriptor import engines

    monkeypatch.setattr(engines, "detect_engine", lambda: "faster-cpu")
    assert engines.make_engine("tiny", amd_gpu=True)._amd_gpu is True  # type: ignore[union-attr]
    assert engines.make_engine("tiny")._amd_gpu is False  # type: ignore[union-attr]
