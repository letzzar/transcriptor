"""Tests del contrato de errores de `Diarizer`.

Regresión real: con un token de HuggingFace caducado, `Pipeline.from_pretrained`
lanzaba `GatedRepoError` (de `huggingface_hub`), que NO es `DiarizationError`.
El worker solo capturaba `DiarizationError`, así que el error se escapaba al
`except` general y **se perdía el archivo entero** en vez de transcribirlo sin
separar hablantes. Ocurrió con 3 audios del Director.

`Diarizer` promete ahora que todo fallo suyo sale como `DiarizationError`.
"""

from __future__ import annotations

import pytest

from transcriptor.pipeline import diarization
from transcriptor.pipeline.diarization import DiarizationError, Diarizer, _explain


class GatedRepoError(Exception):
    """Imita la excepción de huggingface_hub con un token sin acceso."""


def test_fallo_al_cargar_sale_como_diarization_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def revienta(*_args: object, **_kwargs: object) -> None:
        raise GatedRepoError("401 Client Error. Cannot access gated repo")

    monkeypatch.setattr(diarization.config, "get_hf_token", lambda: "hf_loquesea")
    # `load()` importa pyannote dentro; se sustituye el módulo por uno falso.
    import sys
    import types

    falso = types.ModuleType("pyannote.audio")
    falso.Pipeline = type("Pipeline", (), {"from_pretrained": staticmethod(revienta)})
    monkeypatch.setitem(sys.modules, "pyannote.audio", falso)

    with pytest.raises(DiarizationError):
        Diarizer().load()


def test_el_mensaje_de_token_es_accionable() -> None:
    # El fallo probable en campo es el token: el mensaje debe decirlo, no
    # escupir un 401 que no ayuda a nadie.
    mensaje = _explain(GatedRepoError("401 Client Error. Cannot access gated repo"))
    assert "token" in mensaje.lower()
    assert "401" not in mensaje


def test_el_mensaje_de_red_distingue_el_caso() -> None:
    mensaje = _explain(OSError("Connection timeout while contacting host"))
    assert "conexión" in mensaje.lower()


def test_un_error_desconocido_conserva_el_detalle() -> None:
    # Si no sabemos clasificarlo, no se oculta: el detalle va al log.
    mensaje = _explain(ValueError("algo muy raro"))
    assert "algo muy raro" in mensaje
    assert "ValueError" in mensaje


def test_sin_token_sigue_avisando_antes_de_intentarlo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(diarization.config, "get_hf_token", lambda: "")
    with pytest.raises(DiarizationError, match="token"):
        Diarizer().load()
