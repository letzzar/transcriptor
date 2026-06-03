"""Tests offline de gestión de caché en `models.downloader`.

Usan una caché falsa en `tmp_path` (monkeypatch de `config.get_models_cache_dir`)
para no tocar red ni la caché real del usuario. `verify()` necesita red, así que
solo se cubre su rama de "no descargado".
"""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptor import config
from transcriptor.models import downloader, registry


@pytest.fixture
def fake_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(config, "get_models_cache_dir", lambda: tmp_path)
    return tmp_path


def _make_fake_model(cache: Path, model_id: str, payload: bytes) -> None:
    repo = registry.resolve(model_id)
    snap = cache / f"models--{repo.replace('/', '--')}" / "snapshots" / "abc123"
    snap.mkdir(parents=True)
    (snap / "model.bin").write_bytes(payload)


def test_is_downloaded_y_tamano(fake_cache: Path) -> None:
    assert not downloader.is_downloaded("tiny")
    assert downloader.local_size_bytes("tiny") == 0

    _make_fake_model(fake_cache, "tiny", b"x" * 2048)
    assert downloader.is_downloaded("tiny")
    assert downloader.local_size_bytes("tiny") == 2048


def test_delete_libera_y_borra(fake_cache: Path) -> None:
    _make_fake_model(fake_cache, "tiny", b"y" * 4096)
    freed = downloader.delete("tiny")
    assert freed == 4096
    assert not downloader.is_downloaded("tiny")


def test_delete_no_descargado_es_noop(fake_cache: Path) -> None:
    assert downloader.delete("tiny") == 0


def test_verify_no_descargado_es_false(fake_cache: Path) -> None:
    assert downloader.verify("tiny") is False
