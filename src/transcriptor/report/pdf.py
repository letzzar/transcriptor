"""Reporte PDF consolidado de auditoría con fpdf2 y UTF-8 real.

Embebe DejaVu Sans (regular/bold) y DejaVu Sans Mono para renderizar acentos,
eñes y comillas tipográficas correctamente. Corrige el bug del prototipo
(`texto.encode('latin-1', 'replace')`) que perdía esos caracteres.

`consolidate(folder)` une todos los `*_ANALIZADO.txt` + el resumen ejecutivo en
un único `CONSOLIDADO_<fecha>.pdf` y archiva los originales en `PROCESADOS/`.
"""

from __future__ import annotations

import datetime
import shutil
from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from transcriptor.report.txt import ANALYSIS_SUFFIX, SUMMARY_FILENAME

_FONTS_DIR = Path(__file__).resolve().parent.parent / "resources" / "fonts"
_TITLE = "REPORTE CONSOLIDADO DE AUDITORÍA DE AUDIO"


class ReportError(RuntimeError):
    """No hay informes que unificar o falló la generación del PDF."""


class _AuditPdf(FPDF):
    """PDF con cabecera de título y pie con número de página."""

    def header(self) -> None:
        self.set_font("DejaVu", "B", 12)
        self.cell(0, 10, _TITLE, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(4)

    def footer(self) -> None:
        self.set_y(-15)
        self.set_font("DejaVu", "", 8)
        self.cell(0, 10, f"Página {self.page_no()}", align="C")


def _new_pdf() -> _AuditPdf:
    pdf = _AuditPdf()
    # Las fuentes deben registrarse antes del primer add_page (que llama header).
    pdf.add_font("DejaVu", "", str(_FONTS_DIR / "DejaVuSans.ttf"))
    pdf.add_font("DejaVu", "B", str(_FONTS_DIR / "DejaVuSans-Bold.ttf"))
    pdf.add_font("DejaVuMono", "", str(_FONTS_DIR / "DejaVuSansMono.ttf"))
    pdf.set_auto_page_break(auto=True, margin=15)
    return pdf


def build_consolidated(
    analysis_files: list[Path],
    summary_file: Path | None,
    output: Path,
) -> Path:
    """Construye el PDF a partir de los informes de texto (UTF-8 directo)."""
    pdf = _new_pdf()
    pdf.add_page()

    if summary_file is not None:
        pdf.set_font("DejaVuMono", "", 11)
        pdf.cell(0, 6, "RESUMEN EJECUTIVO", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("DejaVuMono", "", 8)
        pdf.multi_cell(0, 4, summary_file.read_text(encoding="utf-8"))
        pdf.add_page()

    for path in analysis_files:
        pdf.set_font("DejaVu", "B", 10)
        pdf.cell(0, 8, f"ORIGEN: {path.name}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("DejaVu", "", 9)
        pdf.multi_cell(0, 5, path.read_text(encoding="utf-8"))
        pdf.ln(3)

    pdf.output(str(output))
    return output


def find_reports(folder: Path) -> tuple[list[Path], Path | None]:
    """Localiza los `*_ANALIZADO.txt` (ordenados) y el resumen ejecutivo."""
    analysis = sorted(folder.glob(f"*{ANALYSIS_SUFFIX}"))
    summary = folder / SUMMARY_FILENAME
    return analysis, (summary if summary.exists() else None)


def consolidate(folder: Path, *, archive: bool = True) -> Path:
    """Une los informes de `folder` en un PDF y archiva los originales.

    Returns:
        Ruta del PDF generado.

    Raises:
        ReportError: si no hay ningún informe que unificar.
    """
    analysis, summary = find_reports(folder)
    if not analysis and summary is None:
        raise ReportError("No hay informes (_ANALIZADO.txt) que unificar en la carpeta.")

    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    output = folder / f"CONSOLIDADO_{stamp}.pdf"
    build_consolidated(analysis, summary, output)

    if archive:
        processed = folder / "PROCESADOS"
        processed.mkdir(exist_ok=True)
        for path in [*analysis, *([summary] if summary else [])]:
            shutil.move(str(path), str(processed / path.name))

    return output
