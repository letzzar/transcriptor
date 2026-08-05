"""Tests de `_combine`: cómo se decide el sexo con el modelo y el pitch.

Fija dos decisiones tomadas con mediciones, para que no se reviertan sin ellas:

1. El F0 CORRIGE al modelo cuando es concluyente. wav2vec2 sesga a "mujer" en
   audio telefónico (banda 300-3400 Hz, sin la fundamental masculina), y esta
   corrección se validó en su día sobre grabaciones reales.

2. NO se exige que modelo y F0 coincidan. Se probó y se descartó con datos:
   la cobertura caía a la mitad (76 → 42 frases etiquetadas) y la tasa de
   error se quedaba igual (11% → 10%), porque con frases cortas ambos
   indicadores fallan a la vez. Salía perdiendo el informe sin ganar
   fiabilidad.
"""

from __future__ import annotations

from transcriptor.pipeline.gender import INDETERMINATE, _combine

F0_HOMBRE = 120.0  # por debajo de _F0_MALE_MAX (175)
F0_MUJER = 220.0  # por encima de _F0_FEMALE_MIN (200)
F0_AMBIGUO = 185.0  # banda de solape 175-200


def test_el_pitch_corrige_al_modelo() -> None:
    # El caso del audio telefónico: el modelo dice "mujer", el pitch dice que no.
    etiqueta, _ = _combine("mujer", 0.95, F0_HOMBRE)
    assert etiqueta == "hombre"


def test_el_pitch_tambien_corrige_en_sentido_contrario() -> None:
    etiqueta, _ = _combine("hombre", 0.95, F0_MUJER)
    assert etiqueta == "mujer"


def test_modelo_seguro_decide_si_el_pitch_calla() -> None:
    etiqueta, _ = _combine("hombre", 0.9, None)
    assert etiqueta == "hombre"


def test_modelo_dudoso_y_sin_pitch_no_se_moja() -> None:
    etiqueta, _ = _combine("hombre", 0.5, None)
    assert etiqueta == INDETERMINATE


def test_banda_de_solape_deja_decidir_al_modelo() -> None:
    # Entre 175 y 200 Hz el pitch no distingue: manda el modelo si va seguro.
    etiqueta, _ = _combine("mujer", 0.9, F0_AMBIGUO)
    assert etiqueta == "mujer"


def test_banda_de_solape_con_modelo_dudoso() -> None:
    etiqueta, _ = _combine("mujer", 0.6, F0_AMBIGUO)
    assert etiqueta == INDETERMINATE
