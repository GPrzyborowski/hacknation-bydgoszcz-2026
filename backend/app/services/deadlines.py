"""Terminy ustawowe (u.d.i.p., KPA), dni wolne od pracy i zapis dat w pismach urzędu."""
import calendar
import re
from datetime import date, datetime, timedelta
from functools import cache

import config
from domain import CaseStatus, LetterKind, Urgency
from errors import BadRequest

ANSWER_DAYS = 14  # art. 13 ust. 1 u.d.i.p.
EXTENSION_MONTHS = 2  # art. 13 ust. 2 u.d.i.p.
CLARIFICATION_REPLY_DAYS = 7  # termin na doprecyzowanie wniosku (art. 64 § 2 KPA)
SOON_DAYS = 3
DEPARTMENT_LEAD_DAYS = 7
DEPARTMENT_MIN_DAYS = 2

EXTENSION_LIMIT_MESSAGE = "Termin nie może przekraczać 2 miesięcy od dnia złożenia wniosku (art. 13 ust. 2 u.d.i.p.)."

MONTHS_GENITIVE = (
    "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
    "lipca", "sierpnia", "września", "października", "listopada", "grudnia",
)
_MONTH_NUMBERS = {name: number for number, name in enumerate(MONTHS_GENITIVE, 1)} | {"wrzesnia": 9, "pazdziernika": 10}


def today() -> date:
    return date.today()


# --- dni wolne od pracy -------------------------------------------------------------------------

def _easter_sunday(year: int) -> date:
    """Algorytm Meeusa/Jonesa/Butchera."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


@cache
def public_holidays(year: int) -> frozenset[date]:
    """Dni ustawowo wolne od pracy (stan od 2025 r., z Wigilią)."""
    fixed = [(1, 1), (1, 6), (5, 1), (5, 3), (8, 15), (11, 1), (11, 11), (12, 24), (12, 25), (12, 26)]
    easter = _easter_sunday(year)
    # Wielkanoc, Poniedziałek Wielkanocny, Zesłanie Ducha Świętego, Boże Ciało.
    movable = [easter + timedelta(days=offset) for offset in (0, 1, 49, 60)]
    return frozenset({date(year, month, day) for month, day in fixed} | set(movable))


def is_non_working(day: date) -> bool:
    return day.weekday() >= 5 or day in public_holidays(day.year)


def shift_to_working_day(day: date) -> date:
    while is_non_working(day):
        day += timedelta(days=1)
    return day


def non_working_days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=n) for n in range((end - start).days + 1) if is_non_working(start + timedelta(days=n))]


# --- terminy sprawy -------------------------------------------------------------------------------

def _apply_shift_rule(day: date) -> date:
    return shift_to_working_day(day) if config.DEADLINE_SHIFT_TO_WORKING_DAY else day


def default_deadline(received: date) -> date:
    return _apply_shift_rule(received + timedelta(days=ANSWER_DAYS))


def extended_deadline(received: date) -> date:
    """Najpóźniejszy dopuszczalny termin po przedłużeniu: 2 miesiące od dnia złożenia wniosku."""
    month_index = received.month - 1 + EXTENSION_MONTHS
    year, month = received.year + month_index // 12, month_index % 12 + 1
    day = min(received.day, calendar.monthrange(year, month)[1])
    return _apply_shift_rule(date(year, month, day))


def days_remaining(deadline: date | None) -> int | None:
    return None if deadline is None else (deadline - today()).days


def urgency(deadline: date | None, status: str | None = None) -> Urgency:
    if status == CaseStatus.odpowiedz_wyslana:
        return Urgency.done
    remaining = days_remaining(deadline)
    if remaining is None:
        return Urgency.normal
    if remaining < 0:
        return Urgency.overdue
    if remaining == 0:
        return Urgency.today
    if remaining == 1:
        return Urgency.tomorrow
    if remaining <= SOON_DAYS:
        return Urgency.soon
    return Urgency.normal


def deadline_note(deadline: date | None) -> str | None:
    if deadline is None or not is_non_working(deadline):
        return None
    return (
        f"Termin przypada w dzień wolny ({format_short(deadline)}) — zgodnie z art. 57 § 4 KPA mógłby upłynąć "
        f"{format_short(shift_to_working_day(deadline))}; bezpieczniej wysłać odpowiedź wcześniej."
    )


def suggestion(received: date) -> dict:
    deadline = default_deadline(received)
    return {
        "received_date": received.isoformat(),
        "deadline_date": deadline.isoformat(),
        "max_extended_deadline": extended_deadline(received).isoformat(),
        "days_remaining": days_remaining(deadline),
        "urgency": urgency(deadline),
        "note": deadline_note(deadline),
    }


def ensure_within_extension_limit(received: date | None, deadline: date | None) -> None:
    if received and deadline and deadline > extended_deadline(received):
        raise BadRequest(EXTENSION_LIMIT_MESSAGE)


def check_extension(received: date, new_deadline: date) -> str | None:
    """Kontrola kwerendy z art. 13 ust. 2. Zwraca ostrzeżenie, gdy zawiadomienie byłoby spóźnione."""
    original = default_deadline(received)
    if new_deadline <= original:
        raise BadRequest(f"Nowy termin musi być późniejszy niż termin 14-dniowy ({format_short(original)}).")
    if today() > original:
        return (
            f"Termin 14-dniowy minął {format_short(original)}. Zgodnie z art. 13 ust. 2 u.d.i.p. powiadomienie "
            "o przedłużeniu powinno zostać wysłane przed jego upływem — zawiadomienie będzie spóźnione."
        )
    return None


def proposed_letter_deadline(kind: LetterKind, received: date) -> date:
    """Kwerenda: najpóźniejszy termin ustawowy. Doprecyzowanie: 7 dni na odpowiedź + 14 dni na rozpatrzenie."""
    limit = extended_deadline(received)
    if kind == LetterKind.kwerenda:
        return limit
    return min(today() + timedelta(days=CLARIFICATION_REPLY_DAYS + ANSWER_DAYS), limit)


def department_reply_deadline(deadline: date) -> date:
    """Termin dla wydziału: tydzień przed terminem ustawowym, nie wcześniej niż za 2 dni, w dzień roboczy."""
    earliest = today() + timedelta(days=DEPARTMENT_MIN_DAYS)
    return shift_to_working_day(max(deadline - timedelta(days=DEPARTMENT_LEAD_DAYS), earliest))


# --- zapis i odczyt dat -------------------------------------------------------------------------------

def format_long(day: date) -> str:
    """„14 stycznia 2026” — zapis dat w pismach UMB."""
    return f"{day.day} {MONTHS_GENITIVE[day.month - 1]} {day.year}"


def format_short(day: date) -> str:
    return day.strftime("%d.%m.%Y")


def format_short_iso(value: str | None, placeholder: str) -> str:
    day = from_iso(value)
    return format_short(day) if day else placeholder


def from_iso(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


_NUMERIC_DATE_PATTERNS = [
    (re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"), ("y", "m", "d")),
    (re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{4})\b"), ("d", "m", "y")),
    (re.compile(r"\b(\d{1,2})[./-](\d{1,2})[./-](\d{2})\b"), ("d", "m", "yy")),
]
_WORD_DATE = re.compile(r"\b(\d{1,2})\s+(" + "|".join(_MONTH_NUMBERS) + r")\s+(\d{4})", re.IGNORECASE)
_PLAIN_DATE_MAX_LENGTH = 12


def parse_date(value) -> tuple[date | None, str | None]:
    """Data z komórki arkusza lub tekstu pisma. Zwraca (data, ostrzeżenie); przy kilku datach — ostatnią."""
    if value is None or value == "":
        return None, None
    if isinstance(value, datetime):
        return value.date(), None
    if isinstance(value, date):
        return value, None

    text = str(value).strip()
    found = _numeric_dates(text) or _word_dates(text)
    if not found:
        return None, f"Nie rozpoznano daty: „{text[:80]}”"
    warning = None
    if len(found) > 1 or len(text) > _PLAIN_DATE_MAX_LENGTH:
        warning = f"Data z dopiskiem w arkuszu: „{text[:120]}” — przyjęto {found[-1].isoformat()}"
    return found[-1], warning


def _numeric_dates(text: str) -> list[date]:
    for pattern, order in _NUMERIC_DATE_PATTERNS:
        found = []
        for match in pattern.finditer(text):
            parts = dict(zip(order, match.groups()))
            year = int(parts["y"]) if "y" in parts else 2000 + int(parts["yy"])
            try:
                found.append(date(year, int(parts["m"]), int(parts["d"])))
            except ValueError:
                continue
        if found:
            return found
    return []


def _word_dates(text: str) -> list[date]:
    found = []
    for match in _WORD_DATE.finditer(text):
        try:
            found.append(date(int(match.group(3)), _MONTH_NUMBERS[match.group(2).lower()], int(match.group(1))))
        except ValueError:
            continue
    return found
