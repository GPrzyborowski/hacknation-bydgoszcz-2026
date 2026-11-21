"""Podział aktów prawnych (ustaw, zarządzeń) na artykuły/paragrafy do bazy wiedzy."""
import re

# OCR często czyta „§” jako „$” (np. w Zarządzeniu nr 535/2024 z materiałów UMB).
_OCR_PARAGRAPH = re.compile(r"(?m)^\$\s*(\d+[a-z]?\.)")
_SPLIT = re.compile(r"(?m)^(?=(?:Art\.\s*\d+[a-z]?\.?|§\s*\d+[a-z]?\.?)\s)")
_HEAD = re.compile(r"(Art\.\s*\d+[a-z]?|§\s*\d+[a-z]?)")


def normalize(text: str) -> str:
    return _OCR_PARAGRAPH.sub(r"§ \1", text)


def split_units(text: str, base_title: str, min_len: int = 40) -> list[tuple[str, str]]:
    """Zwraca [(tytuł, treść)] — po jednym wpisie na artykuł/paragraf; preambuła jako osobny wpis."""
    text = normalize(text)
    chunks: list[tuple[str, str]] = []
    for part in _SPLIT.split(text):
        part = part.strip()
        if len(part) < min_len:
            continue
        head = _HEAD.match(part)
        chunks.append((f"{base_title} — {head.group(1)}" if head else f"{base_title} — wstęp", part))
    return chunks if len(chunks) > 1 else [(base_title, text.strip())]
