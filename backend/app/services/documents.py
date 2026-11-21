"""Eksport projektu odpowiedzi do DOCX i PDF. Zamaskowane fragmenty są zastępowane tekstem maski
(oryginalne dane NIE trafiają do pliku) i dodatkowo oznaczane czarnym tłem."""
import io
from datetime import date
from pathlib import Path

import config
from services.anonymization import mask_spans
from services.deadlines import format_pl

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF_MIME = "application/pdf"


def _header(case: dict) -> tuple[str, str]:
    """„Bydgoszcz, dnia 14 stycznia 2026 r.” i znak sprawy — jak w pismach BKS UMB."""
    place_date = f"{config.OFFICE_CITY}, dnia {format_pl(date.today())} r."
    return place_date, case.get("case_number") or "—"


def build_docx(case: dict, text: str, items: list[dict]) -> bytes:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
    from docx.shared import Pt, RGBColor

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Arial"
    style.font.size = Pt(11)

    for i, line in enumerate(config.OFFICE_LETTERHEAD):
        head = doc.add_paragraph()
        head.paragraph_format.space_after = Pt(0)
        run = head.add_run(line)
        run.bold = i == 0
        run.font.size = Pt(11 if i < 2 else 8)
    doc.add_paragraph()
    place_date, case_number = _header(case)
    p = doc.add_paragraph(place_date)
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    doc.add_paragraph(case_number)
    doc.add_paragraph()

    for line in text.split("\n"):
        para = doc.add_paragraph()
        para.paragraph_format.space_after = Pt(4)
        for chunk, masked in mask_spans(line, items):
            run = para.add_run(chunk)
            if masked:
                run.font.highlight_color = WD_COLOR_INDEX.BLACK
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    doc.add_paragraph()
    for line in config.OFFICE_SIGNATURE:
        sig = doc.add_paragraph(line)
        sig.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        sig.paragraph_format.space_after = Pt(0)
    doc.add_paragraph()
    note = doc.add_paragraph("Projekt pisma przygotowany z pomocą Asystenta UDIP — wymaga weryfikacji i podpisu urzędnika.")
    note.runs[0].font.size = Pt(8)
    note.runs[0].italic = True

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def build_pdf(case: dict, text: str, items: list[dict]) -> bytes:
    from fpdf import FPDF

    pdf = FPDF(format="A4")
    pdf.set_margins(25, 20, 20)
    pdf.set_auto_page_break(True, margin=20)
    pdf.add_page()

    font, has_bold = "Helvetica", True
    if Path(config.PDF_FONT_PATH).exists():
        pdf.add_font("DejaVu", "", config.PDF_FONT_PATH)
        has_bold = Path(config.PDF_FONT_BOLD_PATH).exists()
        if has_bold:
            pdf.add_font("DejaVu", "B", config.PDF_FONT_BOLD_PATH)
        font = "DejaVu"
    else:
        # Bez czcionki TTF polskie znaki zostałyby utracone — transliterujemy, żeby PDF się wygenerował.
        text = _ascii(text)

    def t(value: str) -> str:
        return value if font != "Helvetica" else _ascii(value)

    for i, line in enumerate(config.OFFICE_LETTERHEAD):
        pdf.set_font(font, "B" if i == 0 and has_bold else "", size=11 if i < 2 else 8)
        pdf.cell(0, 5 if i < 2 else 4, t(line), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    place_date, case_number = _header(case)
    pdf.set_font(font, size=11)
    pdf.cell(0, 6, t(place_date), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, t(case_number), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)

    line_h = 6
    for line in text.split("\n"):
        if not line.strip():
            pdf.ln(line_h)
            continue
        for chunk, masked in mask_spans(line, items):
            if masked:
                # Maska jako czarny blok z białym napisem; cell nie łamie wiersza, więc przenosimy ręcznie.
                width = pdf.get_string_width(chunk) + 2
                if pdf.get_x() + width > pdf.w - pdf.r_margin:
                    pdf.ln(line_h)
                pdf.set_fill_color(0, 0, 0)
                pdf.set_text_color(255, 255, 255)
                pdf.cell(width, line_h, chunk, fill=True)
                pdf.set_text_color(0, 0, 0)
            else:
                pdf.write(line_h, chunk)
        pdf.ln(line_h)

    pdf.ln(4)
    for line in config.OFFICE_SIGNATURE:
        pdf.cell(0, 6, t(line), align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font(font, size=7)
    note = "Projekt pisma przygotowany z pomocą Asystenta UDIP — wymaga weryfikacji i podpisu urzędnika."
    pdf.multi_cell(0, 4, note if font != "Helvetica" else _ascii(note))
    return bytes(pdf.output())


def _ascii(text: str) -> str:
    table = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ„”–—", "acelnoszzACELNOSZZ\"\"--")
    return text.translate(table).encode("latin-1", "replace").decode("latin-1")
