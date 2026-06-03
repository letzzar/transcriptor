"""Tests de `report.pdf`: generación del PDF consolidado y archivado."""

from __future__ import annotations

from pathlib import Path

import pytest

from transcriptor.report.pdf import ReportError, consolidate
from transcriptor.report.txt import ANALYSIS_SUFFIX, SUMMARY_FILENAME


def _write_sample_reports(folder: Path) -> None:
    # Texto con acentos, eñe y comillas tipográficas (lo que el bug latin-1 rompía).
    (folder / f"audio1{ANALYSIS_SUFFIX}").write_text(
        "Análisis de audio - audio1.m4a\n"
        "Idioma: ES | Limpieza: NO\n"
        "[00:00] (Voz 1): Señor, ¿está usted seguro de la “declaración”?\n",
        encoding="utf-8",
    )
    (folder / SUMMARY_FILENAME).write_text(
        "AUDITORÍA - 2026-06-03\naudio1.m4a | ES | 00:30 | sha256: abc\n",
        encoding="utf-8",
    )


def test_consolidate_genera_pdf_y_archiva(tmp_path: Path) -> None:
    _write_sample_reports(tmp_path)

    pdf_path = consolidate(tmp_path)

    assert pdf_path.exists()
    assert pdf_path.name.startswith("CONSOLIDADO_")
    # Cabecera de un PDF válido.
    assert pdf_path.read_bytes()[:5] == b"%PDF-"
    assert pdf_path.stat().st_size > 1000

    # Los originales se movieron a PROCESADOS/.
    procesados = tmp_path / "PROCESADOS"
    assert (procesados / f"audio1{ANALYSIS_SUFFIX}").exists()
    assert (procesados / SUMMARY_FILENAME).exists()
    assert not (tmp_path / f"audio1{ANALYSIS_SUFFIX}").exists()


def test_consolidate_sin_archivar(tmp_path: Path) -> None:
    _write_sample_reports(tmp_path)
    consolidate(tmp_path, archive=False)
    # Sin archivar, los originales siguen en su sitio.
    assert (tmp_path / f"audio1{ANALYSIS_SUFFIX}").exists()
    assert not (tmp_path / "PROCESADOS").exists()


def test_consolidate_sin_informes_lanza(tmp_path: Path) -> None:
    with pytest.raises(ReportError):
        consolidate(tmp_path)
