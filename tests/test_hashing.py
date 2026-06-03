"""Tests de `pipeline.hashing.sha256_file`."""

from __future__ import annotations

import hashlib
from pathlib import Path

from transcriptor.pipeline.hashing import sha256_file


def test_sha256_coincide_con_hashlib(tmp_path: Path) -> None:
    data = b"auditoria legal de audio " * 5000  # fuerza varios bloques
    f = tmp_path / "muestra.bin"
    f.write_bytes(data)
    assert sha256_file(f) == hashlib.sha256(data).hexdigest()


def test_sha256_archivo_vacio(tmp_path: Path) -> None:
    f = tmp_path / "vacio.bin"
    f.write_bytes(b"")
    assert sha256_file(f) == hashlib.sha256(b"").hexdigest()
