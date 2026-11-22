"""Eksport pisma do DOCX i PDF w układzie pism BKS UMB.

Zamaskowane fragmenty trafiają do pliku wyłącznie jako tekst maski (oryginalne dane nie są zapisywane)
i są dodatkowo oznaczone czarnym tłem.
"""
import io
from datetime import date

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.shared import Pt, RGBColor
from fpdf import FPDF

import config
from services.deadlines import format_long

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF_MIME = "application/pdf"
DRAFT_FOOTER = "Projekt pisma przygotowany z pomocą UDIPilota — wymaga weryfikacji i podpisu urzędnika."
LETTERHEAD_TITLE_LINES = 2

Segments = tuple[tuple[str, bool], ...]

# Bez czcionki TTF fpdf2 zna tylko Latin-1, więc polskie znaki trzeba wtedy transliterować.
_UNICODE_FONT = config.PDF_FONT_PATH.exists()
_UNICODE_BOLD_FONT = _UNICODE_FONT and config.PDF_FONT_BOLD_PATH.exists()
_ASCII_TRANSLATION = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ„”–—", "acelnoszzACELNOSZZ\"\"--")


def _place_and_date() -> str:
    return f"{config.OFFICE_CITY}, dnia {format_long(date.today())} r."


def _lines(segments: Segments) -> list[list[tuple[str, bool]]]:
    """Dzieli fragmenty pisma na wiersze (maski nigdy nie zawierają końca wiersza)."""
    lines: list[list[tuple[str, bool]]] = [[]]
    for text, masked in segments:
        if masked:
            lines[-1].append((text, True))
            continue
        for index, part in enumerate(text.split("\n")):
            if index:
                lines.append([])
            if part:
                lines[-1].append((part, False))
    return lines


def build_docx(case_number: str, segments: Segments) -> bytes:
    document = Document()
    normal = document.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(11)

    for index, line in enumerate(config.OFFICE_LETTERHEAD):
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(0)
        run = paragraph.add_run(line)
        run.bold = index == 0
        run.font.size = Pt(11 if index < LETTERHEAD_TITLE_LINES else 8)
    document.add_paragraph()
    document.add_paragraph(_place_and_date()).alignment = WD_ALIGN_PARAGRAPH.RIGHT
    document.add_paragraph(case_number)
    document.add_paragraph()

    for line in _lines(segments):
        paragraph = document.add_paragraph()
        paragraph.paragraph_format.space_after = Pt(4)
        for text, masked in line:
            run = paragraph.add_run(text)
            if masked:
                run.font.highlight_color = WD_COLOR_INDEX.BLACK
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)

    document.add_paragraph()
    for line in config.OFFICE_SIGNATURE:
        signature = document.add_paragraph(line)
        signature.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        signature.paragraph_format.space_after = Pt(0)
    document.add_paragraph()
    footer = document.add_paragraph(DRAFT_FOOTER).runs[0]
    footer.font.size = Pt(8)
    footer.italic = True

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def build_pdf(case_number: str, segments: Segments) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_margins(25, 20, 20)
    pdf.set_auto_page_break(True, margin=20)
    pdf.add_page()

    font = "Helvetica"
    if _UNICODE_FONT:
        font = "DejaVu"
        pdf.add_font(font, "", str(config.PDF_FONT_PATH))
        if _UNICODE_BOLD_FONT:
            pdf.add_font(font, "B", str(config.PDF_FONT_BOLD_PATH))

    def printable(text: str) -> str:
        if _UNICODE_FONT:
            return text
        return text.translate(_ASCII_TRANSLATION).encode("latin-1", "replace").decode("latin-1")

    for index, line in enumerate(config.OFFICE_LETTERHEAD):
        title = index < LETTERHEAD_TITLE_LINES
        bold = index == 0 and (_UNICODE_BOLD_FONT or not _UNICODE_FONT)
        pdf.set_font(font, "B" if bold else "", size=11 if title else 8)
        pdf.cell(0, 5 if title else 4, printable(line), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.set_font(font, size=11)
    pdf.cell(0, 6, printable(_place_and_date()), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, printable(case_number), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    line_height = 6
    for line in _lines(segments):
        if not any(text.strip() for text, _ in line):
            pdf.ln(line_height)
            continue
        for text, masked in line:
            if not masked:
                pdf.write(line_height, printable(text))
                continue
            # Maska to czarny blok z białym napisem; cell() nie łamie wiersza, więc przenosimy go ręcznie.
            width = pdf.get_string_width(printable(text)) + 2
            if pdf.get_x() + width > pdf.w - pdf.r_margin:
                pdf.ln(line_height)
            pdf.set_fill_color(0, 0, 0)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(width, line_height, printable(text), fill=True)
            pdf.set_text_color(0, 0, 0)
        pdf.ln(line_height)

    pdf.ln(4)
    for line in config.OFFICE_SIGNATURE:
        pdf.cell(0, 6, printable(line), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font(font, size=7)
    pdf.multi_cell(0, 4, printable(DRAFT_FOOTER))
    return bytes(pdf.output())
