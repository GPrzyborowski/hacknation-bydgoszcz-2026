"""Terminy z u.d.i.p. — ta sama logika co frontend/src/lib/deadline.ts."""
import re
from datetime import date, datetime, timedelta

import config

ANSWER_DAYS = 14
EXTENDED_MONTHS = 2


def today() -> date:
    return date.today()


def _easter(year: int) -> date:
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def public_holidays(year: int) -> set[date]:
    fixed = [(1, 1), (1, 6), (5, 1), (5, 3), (8, 15), (11, 1), (11, 11), (12, 24), (12, 25), (12, 26)]
    easter = _easter(year)
    movable = [easter + timedelta(days=o) for o in (0, 1, 49, 60)]
    return {date(year, m, d) for m, d in fixed} | set(movable)


def is_non_working(d: date) -> bool:
    return d.weekday() >= 5 or d in public_holidays(d.year)


def shift_to_working_day(d: date) -> date:
    while is_non_working(d):
        d += timedelta(days=1)
    return d


def default_deadline(received: date) -> date:
    """Data wpływu + 14 dni — tak jak w rejestrze UMB (formuła =E+14).
    Z DEADLINE_SHIFT_TO_WORKING_DAY=true termin w dzień wolny przesuwa się na dzień roboczy (art. 57 § 4 KPA)."""
    day14 = received + timedelta(days=ANSWER_DAYS)
    return shift_to_working_day(day14) if config.DEADLINE_SHIFT_TO_WORKING_DAY else day14


def deadline_note(deadline: date | None) -> str | None:
    """Ostrzeżenie, gdy termin przypada w sobotę, niedzielę lub święto."""
    if deadline is None or not is_non_working(deadline):
        return None
    return (
        f"Termin przypada w dzień wolny ({deadline.strftime('%d.%m.%Y')}) — zgodnie z art. 57 § 4 KPA mógłby upłynąć "
        f"{shift_to_working_day(deadline).strftime('%d.%m.%Y')}; bezpieczniej wysłać odpowiedź wcześniej."
    )


MONTHS_GENITIVE = [
    "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
    "lipca", "sierpnia", "września", "października", "listopada", "grudnia",
]


def format_pl(d: date) -> str:
    """„14 stycznia 2026” — format dat w pismach UMB."""
    return f"{d.day} {MONTHS_GENITIVE[d.month - 1]} {d.year}"


def extended_deadline(received: date) -> date:
    """Maksymalny termin przy przedłużeniu (art. 13 ust. 2): 2 miesiące od wpływu."""
    month = received.month - 1 + EXTENDED_MONTHS
    year = received.year + month // 12
    month = month % 12 + 1
    day = received.day
    while True:
        try:
            limit = date(year, month, day)
            return shift_to_working_day(limit) if config.DEADLINE_SHIFT_TO_WORKING_DAY else limit
        except ValueError:
            day -= 1


def days_remaining(deadline: date | None) -> int | None:
    return None if deadline is None else (deadline - today()).days


def urgency(deadline: date | None, status: str) -> str:
    """Kolor w kalendarzu: overdue / today / tomorrow / soon (≤3 dni) / normal / done."""
    if status == "odpowiedz_wyslana":
        return "done"
    remaining = days_remaining(deadline)
    if remaining is None:
        return "normal"
    if remaining < 0:
        return "overdue"
    if remaining == 0:
        return "today"
    if remaining == 1:
        return "tomorrow"
    if remaining <= 3:
        return "soon"
    return "normal"


_DATE_PATTERNS = [
    (re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"), ("y", "m", "d")),
    (re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b"), ("d", "m", "y")),
    (re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2})\b"), ("d", "m", "yy")),
]

_MONTHS_PL = {
    "stycznia": 1, "lutego": 2, "marca": 3, "kwietnia": 4, "maja": 5, "czerwca": 6,
    "lipca": 7, "sierpnia": 8, "września": 9, "wrzesnia": 9, "października": 10, "pazdziernika": 10,
    "listopada": 11, "grudnia": 12,
}
_WORD_DATE = re.compile(r"\b(\d{1,2})\s+(" + "|".join(_MONTHS_PL) + r")\s+(\d{4})", re.IGNORECASE)


def parse_date(value) -> tuple[date | None, str | None]:
    """Parsuje datę z komórki Excela / tekstu. Zwraca (data, ostrzeżenie)."""
    if value is None or value == "":
        return None, None
    if isinstance(value, datetime):
        return value.date(), None
    if isinstance(value, date):
        return value, None
    text = str(value).strip()
    found: list[date] = []
    for pattern, order in _DATE_PATTERNS:
        for match in pattern.finditer(text):
            parts = dict(zip(order, match.groups()))
            try:
                y = int(parts["y"]) if "y" in parts else 2000 + int(parts["yy"])
                found.append(date(y, int(parts["m"]), int(parts["d"])))
            except ValueError:
                continue
        if found:
            break
    if not found:
        for match in _WORD_DATE.finditer(text):
            try:
                found.append(date(int(match.group(3)), _MONTHS_PL[match.group(2).lower()], int(match.group(1))))
            except ValueError:
                continue
    if not found:
        return None, f"Nie rozpoznano daty: „{text[:80]}”"
    warning = None
    leftover = text
    if len(found) > 1 or len(leftover) > 12:
        warning = f"Data z dopiskiem w arkuszu: „{text[:120]}” — przyjęto {found[-1].isoformat()}"
    # Przy kilku datach (np. termin przedłużony) bierzemy ostatnią.
    return found[-1], warning


def iso(d: date | None) -> str | None:
    return d.isoformat() if d else None


def from_iso(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
