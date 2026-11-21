"""Kandydaci do anonimizacji (regexy z bazy wiedzy + LLM + znane dane wnioskodawcy) i nakładanie masek."""
import re
import sqlite3

import seed_data
from services import names

_EXEMPT = [re.compile(p, re.IGNORECASE) for p in seed_data.ANONYMIZATION_EXEMPT_PATTERNS]


def is_exempt(quote: str) -> bool:
    """Dane instytucji publicznych (nagłówek UMB, e-maile urzędów, adresy jednostek) nie są anonimizowane."""
    q = " ".join(quote.split()).strip(" ,.;")
    return any(p.search(q) for p in _EXEMPT)

DEFAULT_MASK = "[ANONIMIZACJA]"
NAME_CATEGORY = "Imię i nazwisko osoby fizycznej (niepełniącej funkcji publicznej)"

# "Pan Jan Kowalski", "Pani Anna Nowak-Kowalska"
_NAME_AFTER_TITLE = re.compile(
    r"\b(?:Pan|Pani|Panu|Pana|Panią|Wnioskodawca|Wnioskodawczyni)\s+"
    r"([A-ZŁŚŻŹĆŃÓĘĄ][a-ząćęłńóśźż]+(?:\s+[A-ZŁŚŻŹĆŃÓĘĄ][a-ząćęłńóśźż]+(?:-[A-ZŁŚŻŹĆŃÓĘĄ][a-ząćęłńóśźż]+)?))"
)


_PUBLIC_FUNCTION = re.compile(
    r"(?i)\b(?:prezydent\w*|zastępc\w* prezydenta|wiceprezydent\w*|burmistrz\w*|wojewod\w*|marszał\w*|"
    r"starost\w*|radn\w*|przewodnicząc\w* rady|skarbnik\w*|sekretarz\w* miasta|dyrektor\w*|kierownik\w*|naczelnik\w*|"
    r"rzecznik\w*|posł\w*|senator\w*|minist\w*)\b[^.\n]{0,40}$"
)


def categories(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM anonymization_categories WHERE is_active = 1 ORDER BY id")]


def _overlaps(a: dict, b: dict) -> bool:
    return a["start"] < b["end"] and b["start"] < a["end"]


def find_candidates(
    conn: sqlite3.Connection,
    text: str,
    llm_candidates: list[dict] | None = None,
    known_people: list[str] | None = None,
) -> list[dict]:
    """Zwraca listę {quote, category, reason, start, end, mask, active, source} bez nakładających się zakresów."""
    cats = categories(conn)
    mask_for = {c["name"]: c["mask"] for c in cats}
    found: list[dict] = []

    def add(start: int, end: int, category: str, reason: str, source: str) -> None:
        quote = text[start:end]
        if not quote.strip() or (source != "wnioskodawca" and is_exempt(quote)):
            return
        found.append(
            {
                "quote": quote,
                "category": category,
                "reason": reason,
                "start": start,
                "end": end,
                "mask": mask_for.get(category, DEFAULT_MASK),
                "active": True,
                "source": source,
            }
        )

    # 1) Wskazania modelu językowego — lokalizujemy każdy cytat w tekście (wszystkie wystąpienia).
    for cand in llm_candidates or []:
        quote = str(cand.get("quote") or "").strip()
        if len(quote) < 3:
            continue
        category = str(cand.get("category") or "Dane osobowe")
        reason = str(cand.get("reason") or "Wskazanie modelu językowego")
        for m in re.finditer(re.escape(quote), text):
            add(m.start(), m.end(), category, reason, "llm")

    # 2) Znane osoby prywatne (wnioskodawca) — pełne imię i nazwisko oraz samo nazwisko.
    for person in known_people or []:
        person = (person or "").strip()
        if not person or "@" in person or len(person.split()) < 2 or len(person) > 60:
            continue
        for m in re.finditer(re.escape(person), text, flags=re.IGNORECASE):
            add(m.start(), m.end(), NAME_CATEGORY, "Dane wnioskodawcy — osoby prywatnej", "wnioskodawca")

    # 3) Imiona i nazwiska po zwrotach grzecznościowych.
    for m in _NAME_AFTER_TITLE.finditer(text):
        add(m.start(1), m.end(1), NAME_CATEGORY, "Prawdopodobne dane osoby prywatnej — do weryfikacji", "heurystyka")
    # Imię z listy popularnych imion + nazwisko (również w odmianie) lub inicjał + nazwisko.
    for start, end in names.find_people(text):
        add(start, end, NAME_CATEGORY, "Imię i nazwisko — odznacz, jeśli osoba pełni funkcję publiczną", "heurystyka")

    # Osoby pełniące funkcje publiczne (art. 5 ust. 2 zd. 2 u.d.i.p.) — zostają na liście, ale domyślnie odznaczone.
    for cand in found:
        if cand["category"] == NAME_CATEGORY and _PUBLIC_FUNCTION.search(text[max(0, cand["start"] - 60) : cand["start"]]):
            cand["active"] = False
            cand["reason"] = "Osoba pełniąca funkcję publiczną — co do zasady bez anonimizacji (art. 5 ust. 2 u.d.i.p.)"

    # 4) Regexy kategorii z bazy wiedzy (PESEL, e-mail, telefon, adres, rachunek...).
    for cat in cats:
        if not cat["regex"]:
            continue
        try:
            pattern = re.compile(cat["regex"])
        except re.error:
            continue
        for m in pattern.finditer(text):
            add(m.start(), m.end(), cat["name"], f"Wzorzec: {cat['legal_basis']}".strip(), "regex")

    # Usuwamy nakładające się zakresy — wygrywa dłuższy (np. pełny adres zamiast samego numeru).
    found.sort(key=lambda c: (-(c["end"] - c["start"]), c["start"]))
    result: list[dict] = []
    for cand in found:
        if not any(_overlaps(cand, kept) for kept in result):
            result.append(cand)
    result.sort(key=lambda c: c["start"])
    for i, cand in enumerate(result):
        cand["id"] = i
    return result


def apply(text: str, items: list[dict]) -> str:
    """Nakłada aktywne maski (od końca, żeby nie przesuwać indeksów). Ignoruje zakresy spoza tekstu."""
    active = [i for i in items if i.get("active", True)]
    active.sort(key=lambda i: i["start"], reverse=True)
    last_start = len(text) + 1
    out = text
    for item in active:
        start, end = int(item["start"]), int(item["end"])
        if start < 0 or end > len(text) or start >= end or end > last_start:
            continue  # poza tekstem lub nakłada się na już zamaskowany fragment
        out = out[:start] + (item.get("mask") or DEFAULT_MASK) + out[end:]
        last_start = start
    return out


def mask_spans(text: str, items: list[dict]) -> list[tuple[str, bool]]:
    """Dzieli zanonimizowany tekst na fragmenty (tekst, czy_maska) — do czarnego tła w DOCX/PDF."""
    masks = sorted({i.get("mask") or DEFAULT_MASK for i in items if i.get("active", True)}, key=len, reverse=True)
    if not masks:
        return [(text, False)]
    pattern = re.compile("|".join(re.escape(m) for m in masks))
    spans: list[tuple[str, bool]] = []
    pos = 0
    for m in pattern.finditer(text):
        if m.start() > pos:
            spans.append((text[pos : m.start()], False))
        spans.append((m.group(0), True))
        pos = m.end()
    if pos < len(text):
        spans.append((text[pos:], False))
    return spans
