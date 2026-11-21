"""Wyciąganie tekstu z plików: DOCX, PDF (warstwa tekstowa lub OCR), DOC, obrazy, TXT."""
import io
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import config

DOCX_EXT = {".docx"}
PDF_EXT = {".pdf"}
DOC_EXT = {".doc"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}
TEXT_EXT = {".txt", ".md"}

REQUEST_EXTENSIONS = DOCX_EXT | PDF_EXT | DOC_EXT | IMAGE_EXT
KNOWLEDGE_EXTENSIONS = REQUEST_EXTENSIONS | TEXT_EXT

# Strona PDF uznawana za "mającą tekst", gdy ma choć tyle znaków.
MIN_CHARS_PER_PAGE = 25
# Docelowa szerokość obrazu strony pod OCR (A4 w 300 dpi).
OCR_TARGET_WIDTH_PX = 2480


class ExtractionError(Exception):
    """Plik nie nadaje się do odczytu (pusty, zły format) → 400."""


class OcrUnavailable(Exception):
    """Brak warstwy tekstowej i brak możliwości OCR → 422."""


@dataclass
class Extraction:
    text: str
    has_text_layer: bool
    used_ocr: bool

    @property
    def quality(self) -> float:
        return text_quality(self.text)

    @property
    def warning(self) -> str | None:
        if self.used_ocr and self.quality < LOW_QUALITY_THRESHOLD:
            return (
                "OCR odczytał dokument z dużą liczbą błędów (np. pismo odręczne lub słaby skan). "
                "Sprawdź treść i w razie potrzeby wpisz ją ręcznie (pole manual_text)."
            )
        return None

    @property
    def meta(self) -> dict:
        return {
            "has_text_layer": self.has_text_layer,
            "used_ocr": self.used_ocr,
            "text_length": len(self.text),
            "quality": round(self.quality, 2),
            "warning": self.warning,
        }


# Odsetek "sensownych" słów, poniżej którego wynik OCR uznajemy za nieczytelny.
LOW_QUALITY_THRESHOLD = 0.5
_WORD = re.compile(r"^[\(\"„]?[A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]{2,}[\)\".,:;?!”]*$|^[\d.,:/\-]+$")
_VOWELS = set("aeiouyąęóAEIOUYĄĘÓ")


def text_quality(text: str) -> float:
    """Heurystyczna jakość tekstu: udział tokenów wyglądających jak słowa (z samogłoską, nie WIELKIE ŚMIECI)."""
    tokens = text.split()
    if not tokens:
        return 0.0
    good = 0
    for t in tokens:
        if not _WORD.match(t):
            continue
        letters = [c for c in t if c.isalpha()]
        if letters and not any(c in _VOWELS for c in letters):
            continue
        if len(letters) > 4 and all(c.isupper() for c in letters) and len(set(letters)) < len(letters) / 2:
            continue  # "BEREEEERZEEZE" itp.
        good += 1
    return good / len(tokens)


def extension(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def extract(filename: str, data: bytes, allowed: set[str] = REQUEST_EXTENSIONS) -> Extraction:
    if not data:
        raise ExtractionError("Plik jest pusty.")
    ext = extension(filename)
    if ext not in allowed:
        raise ExtractionError(f"Nieobsługiwany format pliku „{ext or filename}”. Dozwolone: {', '.join(sorted(allowed))}.")

    if ext in DOCX_EXT:
        result = Extraction(_docx_text(data), True, False)
    elif ext in PDF_EXT:
        result = _pdf_text(data)
    elif ext in DOC_EXT:
        result = Extraction(_doc_text(data), True, False)
    elif ext in IMAGE_EXT:
        result = Extraction(_ocr_image_bytes(data), False, True)
    else:
        result = Extraction(_decode_text(data), True, False)

    result.text = _normalize(result.text)
    if not result.text.strip():
        if result.used_ocr:
            raise OcrUnavailable("OCR nie rozpoznał tekstu w dokumencie.")
        raise ExtractionError("Nie znaleziono tekstu w dokumencie.")
    return result


def _normalize(text: str) -> str:
    # pdfium zwraca końce wierszy „\r\n” — bez scalenia każdy wiersz dostałby pustą linię.
    lines = [" ".join(line.split()) for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    out: list[str] = []
    for line in lines:
        if line or (out and out[-1]):
            out.append(line)
    return "\n".join(out).strip()


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1250", "iso-8859-2"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _docx_text(data: bytes) -> str:
    try:
        import docx  # python-docx
    except ImportError as exc:  # pragma: no cover
        raise ExtractionError("Brak biblioteki python-docx.") from exc
    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise ExtractionError("Nie udało się otworzyć pliku DOCX (uszkodzony lub inny format).") from exc
    parts = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            cells = []
            for cell in row.cells:
                if cell.text not in cells:
                    cells.append(cell.text)
            parts.append(" | ".join(cells))
    return "\n".join(parts)


def _doc_text(data: bytes) -> str:
    antiword = shutil.which("antiword")
    if not antiword:
        raise ExtractionError("Format .doc wymaga narzędzia antiword na serwerze — zapisz plik jako .docx lub .pdf.")
    with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as tmp:
        tmp.write(data)
        path = tmp.name
    try:
        proc = subprocess.run([antiword, "-w", "0", path], capture_output=True, timeout=60)
    finally:
        Path(path).unlink(missing_ok=True)
    if proc.returncode != 0:
        raise ExtractionError("Nie udało się odczytać pliku .doc.")
    return _decode_text(proc.stdout)


def _pdf_pages_text(data: bytes) -> list[str]:
    """Tekst stron PDF. pdfium poprawnie skleja słowa w pismach UMB (pypdf rozbija je: „infor macji”);
    pypdf zostaje jako zapas."""
    try:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(data)
        try:
            return [pdf[i].get_textpage().get_text_range() for i in range(len(pdf))]
        finally:
            pdf.close()
    except ImportError:
        pass
    except Exception as exc:
        raise ExtractionError("Nie udało się otworzyć pliku PDF (uszkodzony lub zaszyfrowany).") from exc
    try:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            reader.decrypt("")
        return [(page.extract_text() or "") for page in reader.pages]
    except Exception as exc:
        raise ExtractionError("Nie udało się otworzyć pliku PDF (uszkodzony lub zaszyfrowany).") from exc


def _pdf_text(data: bytes) -> Extraction:
    pages = _pdf_pages_text(data)
    text_pages = [len(p.strip()) >= MIN_CHARS_PER_PAGE for p in pages]
    if pages and all(text_pages):
        return Extraction("\n\n".join(pages), True, False)

    # Brak warstwy tekstowej (całkowicie lub na części stron) → OCR tych stron.
    has_any_text = any(text_pages)
    missing = [i for i, ok in enumerate(text_pages) if not ok] or list(range(len(pages)))
    ocr_pages = _ocr_pdf_pages(data, missing)
    merged = [ocr_pages.get(i, pages[i]) if not text_pages[i] else pages[i] for i in range(len(pages))]
    return Extraction("\n\n".join(merged), has_any_text, True)


def _tesseract():
    try:
        import pytesseract
    except ImportError as exc:
        raise OcrUnavailable("Dokument nie ma warstwy tekstowej, a OCR (pytesseract) nie jest zainstalowany.") from exc
    if not shutil.which("tesseract"):
        raise OcrUnavailable("Dokument nie ma warstwy tekstowej, a na serwerze brak programu tesseract (OCR).")
    return pytesseract


def _ocr_image(image) -> str:
    pytesseract = _tesseract()
    try:
        return pytesseract.image_to_string(image, lang=config.OCR_LANG)
    except pytesseract.TesseractError:
        # Brak polskiego modelu → próba z angielskim, lepsze to niż nic.
        return pytesseract.image_to_string(image)


def _ocr_image_bytes(data: bytes) -> str:
    _tesseract()
    from PIL import Image, ImageSequence

    try:
        image = Image.open(io.BytesIO(data))
    except Exception as exc:
        raise ExtractionError("Nie udało się otworzyć obrazu.") from exc
    texts = []
    for frame in ImageSequence.Iterator(image):
        frame = frame.convert("RGB")
        if frame.width > OCR_TARGET_WIDTH_PX * 1.3:
            ratio = OCR_TARGET_WIDTH_PX / frame.width
            frame = frame.resize((OCR_TARGET_WIDTH_PX, int(frame.height * ratio)))
        texts.append(_ocr_image(frame))
    return "\n\n".join(texts)


def _ocr_pdf_pages(data: bytes, indexes: list[int]) -> dict[int, str]:
    _tesseract()
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise OcrUnavailable("Brak biblioteki pypdfium2 do renderowania stron PDF pod OCR.") from exc
    pdf = pdfium.PdfDocument(data)
    result: dict[int, str] = {}
    try:
        for i in indexes:
            if i >= len(pdf):
                continue
            page = pdf[i]
            # Skany bywają zapisane jako strony o nietypowym rozmiarze (np. 1220×1752 pt) — wtedy 300 dpi
            # daje obraz >5000 px, na którym Tesseract nie znajduje tekstu. Normalizujemy do szerokości A4 w 300 dpi.
            width_pt = page.get_width() or 595
            scale = min(300 / 72, OCR_TARGET_WIDTH_PX / width_pt)
            image = page.render(scale=scale).to_pil()
            result[i] = _ocr_image(image)
    finally:
        pdf.close()
    return result
