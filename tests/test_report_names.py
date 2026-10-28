"""Nombres de los informes: dos audios con el mismo nombre no se pisan."""

from __future__ import annotations

from pathlib import Path

from transcriptor.report.txt import analysis_filename, write_analysis
from transcriptor.workers.transcribe_worker import shared_stems


def test_nombre_de_siempre_sin_colision() -> None:
    # Formato del prototipo: no cambia para no romper auditorías ya entregadas.
    assert analysis_filename("a.mp3") == "a_ANALIZADO.txt"


def test_con_colision_se_incluye_la_extension() -> None:
    assert analysis_filename("a.MP3", with_extension=True) == "a_mp3_ANALIZADO.txt"


def test_detecta_nombres_compartidos_sin_distinguir_mayusculas() -> None:
    files = [Path("a.mp3"), Path("A.wav"), Path("b.m4a")]
    assert shared_stems(files) == {"a"}


def test_dos_audios_con_el_mismo_nombre_dejan_dos_informes(tmp_path: Path) -> None:
    files = [Path("a.mp3"), Path("a.wav")]
    repetidos = shared_stems(files)
    for f in files:
        write_analysis(tmp_path, f.name, f.name, with_extension=f.stem.lower() in repetidos)
    informes = sorted(p.name for p in tmp_path.iterdir())
    assert informes == ["a_mp3_ANALIZADO.txt", "a_wav_ANALIZADO.txt"]
    assert (tmp_path / "a_mp3_ANALIZADO.txt").read_text() == "a.mp3"
