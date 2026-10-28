"""find_ffmpeg encuentra Homebrew aunque la app herede el PATH mínimo del Finder."""

from __future__ import annotations

import shutil
import stat

from transcriptor.pipeline import audio


def test_finds_ffmpeg_outside_minimal_path(tmp_path, monkeypatch):
    fake = tmp_path / "ffmpeg"
    fake.write_text("#!/bin/sh\n")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)

    monkeypatch.setenv("PATH", "/usr/bin:/bin:/usr/sbin:/sbin")
    monkeypatch.setattr(audio, "is_windows", lambda: False)
    monkeypatch.setattr(audio, "_UNIX_FFMPEG_DIRS", (str(tmp_path),))
    monkeypatch.chdir(tmp_path.parent)

    assert audio.find_ffmpeg() == str(fake)
    # Y queda en el PATH, porque mlx-whisper lo busca por nombre.
    assert shutil.which("ffmpeg") == str(fake)


def test_returns_none_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(audio, "is_windows", lambda: False)
    monkeypatch.setattr(audio, "_UNIX_FFMPEG_DIRS", (str(tmp_path / "nada"),))
    monkeypatch.chdir(tmp_path)

    assert audio.find_ffmpeg() is None
