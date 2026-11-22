"""Kandydaci do anonimizacji (wskazania modelu, dane wnioskodawcy, heurystyki, wzorce kategorii) i maskowanie tekstu."""
import logging
import re
import sqlite3
from dataclasses import dataclass
from functools import lru_cache

from errors import BadRequest
from seed_data import ANONYMIZATION_EXEMPT_PATTERNS, MASK, NAME_CATEGORY
from services import names
from services.patterns import CAPITALIZED_WORD

log = logging.getLogger(__name__)

PUBLIC_FUNCTION_CONTEXT_CHARS = 60
MIN_QUOTE_LENGTH = 3
MAX_PERSON_NAME_LENGTH = 60

_EXEMPT = [re.compile(pattern, re.IGNORECASE) for pattern in ANONYMIZATION_EXEMPT_PATTERNS]

# „Pan Jan Kowalski”, „Pani Anna Nowak-Kowalska”
_NAME_AFTER_TITLE = re.compile(
    r"\b(?:Pan|Pani|Panu|Pana|Panią|Wnioskodawca|Wnioskodawczyni)\s+"
    rf"({CAPITALIZED_WORD}(?:\s+{CAPITALIZED_WORD}(?:-{CAPITALIZED_WORD})?))"
)

# Funkcja publiczna tuż przed nazwiskiem — art. 5 ust. 2 zd. 2 u.d.i.p. nie chroni takich osób.
_PUBLIC_FUNCTION = re.compile(
    r"(?i)\b(?:prezydent\w*|zastępc\w* prezydenta|wiceprezydent\w*|burmistrz\w*|wojewod\w*|marszał\w*|"
    r"starost\w*|radn\w*|przewodnicząc\w* rady|skarbnik\w*|sekretarz\w* miasta|dyrektor\w*|kierownik\w*|naczelnik\w*|"
    r"rzecznik\w*|posł\w*|senator\w*|minist\w*)\b[^.\n]{0,40}$"
)


@dataclass(frozen=True)
class Redaction:
    """Tekst po anonimizacji jako ciąg fragmentów (treść, czy to maska) — do zapisu i do czarnego tła w plikach."""

    segments: tuple[tuple[str, bool], ...]

    @property
    def text(self) -> str:
        return "".join(segment for segment, _ in self.segments)


def is_exempt(quote: str) -> bool:
    """Dane instytucji publicznych (nagłówek UMB, e-maile urzędów, adresy jednostek) nie są anonimizowane."""
    normalized = " ".join(quote.split()).strip(" ,.;")
    return any(pattern.search(normalized) for pattern in _EXEMPT)


def load_categories(conn: sqlite3.Connection) -> list[dict]:
    return [dict(row) for row in conn.execute("SELECT * FROM anonymization_categories WHERE is_active ORDER BY id")]


@lru_cache(maxsize=128)
def _compile(pattern: str) -> re.Pattern | None:
    try:
        return re.compile(pattern)
    except re.error:
        log.warning("Pominięto niepoprawny wzorzec kategorii anonimizacji: %s", pattern)
        return None


def find_candidates(
    text: str,
    categories: list[dict],
    llm_candidates: list[dict] | None = None,
    known_people: list[str] | None = None,
) -> list[dict]:
    """Kandydaci (schemat AnonymizationCandidate) bez nakładających się zakresów; wygrywa dłuższy fragment."""
    mask_for = {category["name"]: category["mask"] for category in categories}
    found: list[dict] = []

    def add(start: int, end: int, category: str, reason: str, source: str) -> None:
        quote = text[start:end]
        if not quote.strip() or (source != "wnioskodawca" and is_exempt(quote)):
            return
        found.append(
            {
                "quote": quote, "category": category, "reason": reason, "start": start, "end": end,
                "mask": mask_for.get(category, MASK), "active": True, "source": source,
            }
        )

    for candidate in llm_candidates or []:
        quote = str(candidate.get("quote") or "").strip()
        if len(quote) < MIN_QUOTE_LENGTH:
            continue
        category = str(candidate.get("category") or "Dane osobowe")
        reason = str(candidate.get("reason") or "Wskazanie modelu językowego")
        for match in re.finditer(re.escape(quote), text):
            add(match.start(), match.end(), category, reason, "llm")

    for person in (person.strip() for person in known_people or [] if person):
        if "@" in person or len(person.split()) < 2 or len(person) > MAX_PERSON_NAME_LENGTH:
            continue
        for match in re.finditer(re.escape(person), text, flags=re.IGNORECASE):
            add(match.start(), match.end(), NAME_CATEGORY, "Dane wnioskodawcy — osoby prywatnej", "wnioskodawca")

    for match in _NAME_AFTER_TITLE.finditer(text):
        add(match.start(1), match.end(1), NAME_CATEGORY, "Prawdopodobne dane osoby prywatnej — do weryfikacji", "heurystyka")
    for start, end in names.find_people(text):
        add(start, end, NAME_CATEGORY, "Imię i nazwisko — odznacz, jeśli osoba pełni funkcję publiczną", "heurystyka")

    # Osoby pełniące funkcje publiczne zostają na liście, ale domyślnie odznaczone.
    for candidate in found:
        context = text[max(0, candidate["start"] - PUBLIC_FUNCTION_CONTEXT_CHARS) : candidate["start"]]
        if candidate["category"] == NAME_CATEGORY and _PUBLIC_FUNCTION.search(context):
            candidate["active"] = False
            candidate["reason"] = "Osoba pełniąca funkcję publiczną — co do zasady bez anonimizacji (art. 5 ust. 2 u.d.i.p.)"

    for category in categories:
        pattern = _compile(category["regex"]) if category["regex"] else None
        if pattern is None:
            continue
        for match in pattern.finditer(text):
            add(match.start(), match.end(), category["name"], f"Wzorzec: {category['legal_basis']}".strip(), "regex")

    return _without_overlaps(found)


def _without_overlaps(candidates: list[dict]) -> list[dict]:
    kept: list[dict] = []
    for candidate in sorted(candidates, key=lambda c: (-(c["end"] - c["start"]), c["start"])):
        if all(candidate["end"] <= other["start"] or other["end"] <= candidate["start"] for other in kept):
            kept.append(candidate)
    kept.sort(key=lambda c: c["start"])
    return [{**candidate, "id": index} for index, candidate in enumerate(kept)]


def apply(text: str, items: list[dict]) -> Redaction:
    """Nakłada zaznaczone maski. Zakres spoza tekstu to błąd klienta; nakładający się — pomijany."""
    for item in items:
        if not 0 <= item["start"] < item["end"] <= len(text):
            raise BadRequest(f"Zakres anonimizacji {item['start']}–{item['end']} wykracza poza treść pisma.")

    masked: list[dict] = []
    boundary = len(text)
    for item in sorted((item for item in items if item.get("active", True)), key=lambda item: item["start"], reverse=True):
        if item["end"] <= boundary:
            masked.append(item)
            boundary = item["start"]

    segments: list[tuple[str, bool]] = []
    position = 0
    for item in reversed(masked):
        if item["start"] > position:
            segments.append((text[position : item["start"]], False))
        segments.append((item.get("mask") or MASK, True))
        position = item["end"]
    if position < len(text):
        segments.append((text[position:], False))
    return Redaction(tuple(segments))
