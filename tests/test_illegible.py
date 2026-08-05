"""Tests del marcado de tramos ilegibles (`pipeline.merge.display_text`).

Cuando Whisper decodifica con baja confianza, o entra en el bucle repetitivo
típico del audio ruidoso, el informe debe dejar constancia del tramo ilegible
en vez de dar por buena una transcripción inventada.
"""

from __future__ import annotations

from transcriptor.engines.base import Segment
from transcriptor.pipeline.merge import (
    ILLEGIBLE_TEXT,
    Turn,
    assign_speakers,
    display_text,
)


def test_texto_fiable_se_respeta() -> None:
    seg = Segment(text="hola", start=0.0, end=1.0, avg_logprob=-0.3, compression_ratio=1.4)
    assert display_text(seg) == "hola"


def test_baja_confianza_es_ilegible() -> None:
    seg = Segment(text="lo que sea", start=0.0, end=1.0, avg_logprob=-1.5, compression_ratio=1.4)
    assert display_text(seg) == ILLEGIBLE_TEXT


def test_texto_repetitivo_es_ilegible() -> None:
    # compression_ratio alto = el bucle "gracias gracias gracias…" de Whisper.
    seg = Segment(text="gracias " * 40, start=0.0, end=1.0, avg_logprob=-0.2, compression_ratio=6.0)
    assert display_text(seg) == ILLEGIBLE_TEXT


def test_sin_metricas_se_respeta_el_texto() -> None:
    # Un motor que no exponga las métricas no debe provocar falsos ilegibles.
    assert display_text(Segment(text="hola", start=0.0, end=1.0)) == "hola"


def test_limites_exactos_no_marcan() -> None:
    # Los umbrales son estrictos: justo en el límite el texto sigue siendo válido.
    seg = Segment(text="hola", start=0.0, end=1.0, avg_logprob=-1.0, compression_ratio=2.4)
    assert display_text(seg) == "hola"


def test_assign_speakers_aplica_el_marcado() -> None:
    # El criterio debe llegar al informe, no quedarse en la función suelta.
    segments = [
        Segment(text="buenas", start=0.0, end=2.0, avg_logprob=-0.2, compression_ratio=1.1),
        Segment(text="ruido", start=2.0, end=4.0, avg_logprob=-2.0, compression_ratio=1.1),
    ]
    turns = [Turn("SPK_A", 0.0, 4.0)]
    out = assign_speakers(segments, turns, max_speakers=1)
    assert [s.text for s in out] == ["buenas", ILLEGIBLE_TEXT]
    # El tramo ilegible conserva tiempo y hablante: consta que ahí hubo voz.
    assert out[1].start == 2.0
    assert out[1].speaker == "Voz 1"
