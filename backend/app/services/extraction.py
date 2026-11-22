"""Tekst z plików wniosków i materiałów: DOCX, PDF (warstwa tekstowa albo OCR), DOC, skany, TXT."""
import io
import logging
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from functools import cache, cached_property
from pathlib import Path

import docx
import pypdfium2 as pdfium
import pytesseract
from PIL import Image, ImageSequence

import config
from errors import BadRequest, Unprocessable
from services.patterns import PL_LETTER

log = logging.getLogger(__name__)

REQUEST_EXTENSIONS = (".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png", ".tif", ".tiff")
KNOWLEDGE_EXTENSIONS = (*REQUEST_EXTENSIONS, ".txt", ".md")
SPREADSHEET_EXTENSIONS = (".xlsx", ".xlsm")
_IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".tif", ".tiff"})

# Strona PDF z mniejszą liczbą znaków to skan bez warstwy tekstowej.
MIN_CHARS_PER_PAGE = 25
# Odsetek tokenów wyglądających jak słowa, poniżej którego wynik OCR uznajemy za nieczytelny.
LOW_QUALITY_THRESHOLD = 0.5

OCR_DPI = 300
A4_WIDTH_PT = 595
OCR_TARGET_WIDTH_PX = 2480  # szerokość A4 w 300 dpi
OVERSIZED_IMAGE_RATIO = 1.3
DOC_CONVERSION_TIMEOUT_SECONDS = 60

_WORD = re.compile(rf"^[(\"„]?[{PL_LETTER}]{{2,}}[)\".,:;?!”]*$|^[\d.,:/\-]+$")
_VOWELS = frozenset("aeiouyąęóAEIOUYĄĘÓ")


class ExtractionError(BadRequest):
    """Pusty plik, nieobsługiwany format albo uszkodzony dokument."""


class OcrUnavailable(Unprocessable):
    """Dokument bez warstwy tekstowej, którego nie da się odczytać przez OCR."""


@dataclass
class Extraction:
    text: str
    has_text_layer: bool
    used_ocr: bool
    manual: bool = False

    @cached_property
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
    def readable(self) -> bool:
        return self.manual or self.quality >= LOW_QUALITY_THRESHOLD

    @property
    def meta(self) -> dict:
        return {
            "has_text_layer": self.has_text_layer,
            "used_ocr": self.used_ocr,
            "text_length": len(self.text),
            "quality": round(self.quality, 2),
            "warning": self.warning,
            "manual_text_used": self.manual,
        }


def text_quality(text: str) -> float:
    """Udział tokenów wyglądających jak słowa: z samogłoską i bez ciągów wielkich liter typu „BEREEERZEE”."""
    tokens = text.split()
    if not tokens:
        return 0.0
    good = 0
    for token in tokens:
        if not _WORD.match(token):
            continue
        letters = [char for char in token if char.isalpha()]
        if letters and not any(char in _VOWELS for char in letters):
            continue
        if len(letters) > 4 and all(char.isupper() for char in letters) and len(set(letters)) < len(letters) / 2:
            continue
        good += 1
    return good / len(tokens)


def extension(filename: str) -> str:
    return Path(filename or "").suffix.lower()


def manual_text(text: str) -> Extraction:
    """Treść wpisana przez urzędnika, gdy skanu nie da się odczytać (np. pismo odręczne)."""
    return Extraction(text.strip(), has_text_layer=False, used_ocr=False, manual=True)


def extract(filename: str, data: bytes, allowed: tuple[str, ...] = REQUEST_EXTENSIONS) -> Extraction:
    if not data:
        raise ExtractionError("Plik jest pusty.")
    ext = extension(filename)
    if ext not in allowed:
        raise ExtractionError(f"Nieobsługiwany format pliku „{ext or filename}”. Dozwolone: {', '.join(sorted(allowed))}.")

    if ext == ".pdf":
        text, has_text_layer, used_ocr = _pdf_text(data)
    elif ext in _IMAGE_EXTENSIONS:
        text, has_text_layer, used_ocr = _image_text(data), False, True
    elif ext == ".docx":
        text, has_text_layer, used_ocr = _docx_text(data), True, False
    elif ext == ".doc":
        text, has_text_layer, used_ocr = _doc_text(data), True, False
    else:
        text, has_text_layer, used_ocr = _decode(data), True, False

    text = _normalize(text)
    if not text:
        if used_ocr:
            raise OcrUnavailable("OCR nie rozpoznał tekstu w dokumencie.")
        raise ExtractionError("Nie znaleziono tekstu w dokumencie.")
    return Extraction(text, has_text_layer, used_ocr)


def _normalize(text: str) -> str:
    """Pojedyncze spacje w wierszach i najwyżej jeden pusty wiersz z rzędu (pdfium zwraca końce wierszy „\\r\\n”)."""
    lines = [" ".join(line.split()) for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    kept: list[str] = []
    for line in lines:
        if line or (kept and kept[-1]):
            kept.append(line)
    return "\n".join(kept).strip()


def _decode(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1250", "iso-8859-2"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _docx_text(data: bytes) -> str:
    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as exc:
        raise ExtractionError("Nie udało się otworzyć pliku DOCX (uszkodzony lub inny format).") from exc
    parts = [paragraph.text for paragraph in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            # Scalone komórki python-docx zwraca kilka razy — każdą treść bierzemy raz.
            parts.append(" | ".join(dict.fromkeys(cell.text for cell in row.cells)))
    return "\n".join(parts)


def _doc_text(data: bytes) -> str:
    antiword = shutil.which("antiword")
    if not antiword:
        raise ExtractionError("Format .doc wymaga narzędzia antiword na serwerze — zapisz plik jako .docx lub .pdf.")
    with tempfile.NamedTemporaryFile(suffix=".doc", delete=False) as tmp:
        tmp.write(data)
        path = Path(tmp.name)
    try:
        process = subprocess.run([antiword, "-w", "0", str(path)], capture_output=True, timeout=DOC_CONVERSION_TIMEOUT_SECONDS)
    finally:
        path.unlink(missing_ok=True)
    if process.returncode != 0:
        raise ExtractionError("Nie udało się odczytać pliku .doc.")
    return _decode(process.stdout)


def _pdf_text(data: bytes) -> tuple[str, bool, bool]:
    """Warstwa tekstowa z pdfium (poprawnie skleja słowa w pismach UMB); strony bez niej przez OCR."""
    try:
        document = pdfium.PdfDocument(data)
    except Exception as exc:
        raise ExtractionError("Nie udało się otworzyć pliku PDF (uszkodzony lub zaszyfrowany).") from exc
    try:
        pages = [document[index].get_textpage().get_text_range() for index in range(len(document))]
        scanned = [index for index, text in enumerate(pages) if len(text.strip()) < MIN_CHARS_PER_PAGE]
        for index in scanned:
            pages[index] = _ocr(_render_for_ocr(document[index]))
    finally:
        document.close()
    return "\n\n".join(pages), len(scanned) < len(pages), bool(scanned)


def _render_for_ocr(page) -> Image.Image:
    # Skany bywają stronami o nietypowym rozmiarze (np. 1220×1752 pt). W 300 dpi dałyby obraz szerszy niż 5000 px,
    # na którym Tesseract nie znajduje tekstu, dlatego normalizujemy szerokość do A4.
    scale = min(OCR_DPI / 72, OCR_TARGET_WIDTH_PX / (page.get_width() or A4_WIDTH_PT))
    return page.render(scale=scale, grayscale=True).to_pil()


def _image_text(data: bytes) -> str:
    _require_tesseract()
    try:
        image = Image.open(io.BytesIO(data))
    except Exception as exc:
        raise ExtractionError("Nie udało się otworzyć obrazu.") from exc
    return "\n\n".join(_ocr(_fit_width(frame.convert("L"))) for frame in ImageSequence.Iterator(image))


def _fit_width(image: Image.Image) -> Image.Image:
    if image.width <= OCR_TARGET_WIDTH_PX * OVERSIZED_IMAGE_RATIO:
        return image
    return image.resize((OCR_TARGET_WIDTH_PX, int(image.height * OCR_TARGET_WIDTH_PX / image.width)))


def _ocr(image: Image.Image) -> str:
    _require_tesseract()
    return pytesseract.image_to_string(image, lang=_ocr_language())


def _require_tesseract() -> None:
    if not _tesseract_installed():
        raise OcrUnavailable("Dokument nie ma warstwy tekstowej, a na serwerze brak programu tesseract (OCR).")


@cache
def _tesseract_installed() -> bool:
    return shutil.which("tesseract") is not None


@cache
def _ocr_language() -> str | None:
    """Polski model OCR; gdy go brak — domyślny model Tesseracta, lepszy niż żaden."""
    if config.OCR_LANG in pytesseract.get_languages():
        return config.OCR_LANG
    log.warning("Brak modelu OCR „%s” — używam domyślnego języka Tesseracta.", config.OCR_LANG)
    return None
