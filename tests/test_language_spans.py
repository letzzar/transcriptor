"""Tests de la detección de idioma por ventana (`engines.mlx_engine`).

Regresión del fallo real: un audio de 36 minutos en castellano se decodificaba
entero en catalán porque la PRIMERA ventana de 30 s se detectó como `ca`. Las
secuencias de estos tests salen de mediciones sobre ese audio.
"""

from __future__ import annotations

from transcriptor.engines.mlx_engine import _LANGUAGE_HYSTERESIS, _apply_hysteresis


def test_ventana_inicial_erronea_no_contamina() -> None:
    # El fallo original: 'ca' suelto al principio de un audio en castellano.
    crudos = ["ca", "es", "es", "es", "es"]
    assert _apply_hysteresis(crudos) == ["es"] * 5


def test_deteccion_espuria_aislada_se_descarta() -> None:
    # Medido: ru=0.925 y pt=0.883 en ventanas sueltas. Alta confianza, y falsas.
    crudos = ["es", "es", "ru", "es", "es", "pt", "es"]
    assert _apply_hysteresis(crudos) == ["es"] * 7


def test_cambio_sostenido_se_acepta() -> None:
    # Un cambio real de idioma dura: debe respetarse desde donde empieza.
    crudos = ["es", "es", "ca", "ca", "ca"]
    assert _apply_hysteresis(crudos) == ["es", "es", "ca", "ca", "ca"]


def test_vuelve_al_idioma_anterior() -> None:
    crudos = ["es", "es", "en", "en", "es", "es"]
    assert _apply_hysteresis(crudos) == ["es", "es", "en", "en", "es", "es"]


def test_zona_ruidosa_mantiene_el_idioma_vigente() -> None:
    # Medido entre los minutos 6,5 y 11: gl/it/en/pt alternando sin repetirse.
    # Nada se sostiene, así que debe quedarse en el idioma que ya venía.
    crudos = ["es", "es", "gl", "it", "en", "es", "pt", "it", "es"]
    salida = _apply_hysteresis(crudos)
    assert salida == ["es"] * 9


def test_audio_sin_idioma_estable() -> None:
    # Si NADA se repite, no se puede decidir: se usa la primera ventana y se
    # mantiene, en vez de trocear el audio en tramos de un idioma distinto cada uno.
    crudos = ["es", "ru", "fi", "el"]
    assert len(set(_apply_hysteresis(crudos))) == 1


def test_una_sola_ventana() -> None:
    assert _apply_hysteresis(["es"]) == ["es"]


def test_la_histeresis_es_de_al_menos_dos_ventanas() -> None:
    # Con 1 no habría filtrado alguno y volvería el fallo original.
    assert _LANGUAGE_HYSTERESIS >= 2
