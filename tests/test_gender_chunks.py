"""Tests del troceado de la clasificación de género (`pipeline.gender`).

Regresión del cuelgue en Mac: se pasaba a wav2vec2 todo el audio de un hablante
de una sola vez (~48 MB de RAM por segundo, sin techo), y una grabación de 30
minutos agotaba la memoria del equipo. El troceado acota el pico.
"""

from __future__ import annotations

import numpy as np

from transcriptor.pipeline.gender import (
    _CHUNK_SECONDS,
    _MAX_CHUNKS,
    _sample_chunks,
)

SR = 16000


def test_audio_corto_se_devuelve_entero() -> None:
    samples = np.zeros(int(3 * SR), dtype=np.float32)
    chunks = _sample_chunks(samples, SR)
    assert len(chunks) == 1
    assert chunks[0].size == samples.size


def test_audio_largo_se_acota_en_numero_y_tamano() -> None:
    # 30 minutos: el caso que colgaba el equipo.
    samples = np.zeros(int(1800 * SR), dtype=np.float32)
    chunks = _sample_chunks(samples, SR)
    assert len(chunks) == _MAX_CHUNKS
    assert all(c.size == int(_CHUNK_SECONDS * SR) for c in chunks)


def test_los_trozos_cubren_toda_la_grabacion() -> None:
    # Deben repartirse de principio a fin, no amontonarse al inicio: si no, una
    # voz se juzgaría por sus primeros segundos.
    size = int(600 * SR)
    samples = np.arange(size, dtype=np.float32)
    chunks = _sample_chunks(samples, SR)
    assert chunks[0][0] == 0.0
    assert chunks[-1][-1] == float(size - 1)


def test_los_trozos_son_vistas_sin_copiar() -> None:
    # El troceado no debe duplicar el audio en memoria.
    samples = np.zeros(int(600 * SR), dtype=np.float32)
    assert all(c.base is samples for c in _sample_chunks(samples, SR))


def test_pico_de_memoria_acotado() -> None:
    # Lo que de verdad se quería arreglar: el trozo mayor no crece con la
    # duración total del audio.
    corto = _sample_chunks(np.zeros(int(60 * SR), dtype=np.float32), SR)
    largo = _sample_chunks(np.zeros(int(3600 * SR), dtype=np.float32), SR)
    assert max(c.size for c in largo) == max(c.size for c in corto)
