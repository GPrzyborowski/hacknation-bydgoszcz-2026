"""Import rejestru spraw z arkusza .xlsx (np. „WNIOSKI O UDOSTĘPNIANIE INFORMACJI PUBLICZNEJ.xlsx”).

Kolumny są rozpoznawane po nagłówkach, w dowolnej kolejności. Daty z dopiskami są parsowane z ostrzeżeniem
(date_parse_warning), a niespójności rejestru są zgłaszane, nie poprawiane po cichu.
"""
import io
import re
import unicodedata

from openpyxl import load_workbook

from domain import CaseStatus, ProcedureMode
from errors import BadRequest
from services import deadlines
from services.case_store import year_from_case_number

HEADER_SEARCH_ROWS = 15

# Kolejność ma znaczenie: bardziej szczegółowe wzorce przed ogólnymi („data odpowiedzi” przed „odpowiedź”).
COLUMN_PATTERNS: list[tuple[str, list[str]]] = [
    ("ordinal", [r"^lp\.?$", r"^l\.\s?p\.?$", r"liczba porz"]),
    ("response_date", [r"data (udziel|wysl|odpowiedz|zalatw)", r"udzielenia odp", r"data odp"]),
    ("deadline_date", [r"termin"]),
    ("received_date", [r"wplyw", r"data (zlozenia|wniosku|otrzym)", r"^data$"]),
    ("case_number", [r"znak", r"sygnatur", r"nr (wniosku|sprawy)", r"numer", r"^nr\.?$"]),
    ("applicant", [r"wnioskodaw", r"imie", r"nazwa", r"od kogo"]),
    ("subject", [r"temat", r"przedmiot", r"opis", r"dotyczy", r"tresc wniosku", r"zakres"]),
    ("departments", [r"wydzial", r"komork", r"biur", r"jednost"]),
    ("initials", [r"inicjal", r"prowadz", r"osoba", r"referent"]),
    ("procedure_mode", [r"tryb", r"sposob zalatw"]),
    ("status", [r"status", r"etap", r"stan"]),
    ("response_text", [r"odpowiedz", r"tresc odp"]),
    ("notes", [r"uwag"]),
]

PROCEDURE_MODE_KEYWORDS = {
    "bip": ProcedureMode.bip,
    "przetworz": ProcedureMode.przetworzona,
    "odmow": ProcedureMode.odmowa,
    "dysponent": ProcedureMode.nie_dysponent,
    "nie posiada": ProcedureMode.nie_dysponent,
}

STATUS_KEYWORDS = [
    (CaseStatus.odpowiedz_wyslana, ["wysłan", "udzielon", "zakończ", "zalatw", "załatw"]),
    (CaseStatus.przygotowana_odpowiedz, ["przygotowan"]),
    (CaseStatus.odpowiedz_w_przygotowaniu, ["w przygotowaniu", "w trakcie"]),
    (CaseStatus.kwerenda, ["kwerend", "przedłuż"]),
    (CaseStatus.doprecyzowanie, ["doprecyz", "wezwan", "uzupełn"]),
    (CaseStatus.zapytania_wyslane, ["zapytan", "przekazan", "wydział"]),
]


def parse_workbook(data: bytes, known_departments: set[str]) -> tuple[list[dict], list[str]]:
    """Zwraca (rekordy spraw z listą symboli wydziałów pod kluczem "departments", ostrzeżenia)."""
    try:
        workbook = load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    except Exception as exc:
        raise BadRequest("Nie udało się otworzyć pliku .xlsx.") from exc

    records: list[dict] = []
    warnings: list[str] = []
    for sheet in workbook.worksheets:
        rows = list(sheet.iter_rows(values_only=True))
        header = _find_header(rows)
        if header is None:
            warnings.append(f"Arkusz „{sheet.title}”: nie znaleziono wiersza nagłówka — pominięto.")
            continue
        header_index, columns = header
        for row_number, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
            record = _parse_row(row, columns, known_departments, sheet.title, row_number)
            if record is None:
                continue
            if record["year"] is None:
                warnings.append(f"Arkusz „{sheet.title}”, wiersz {row_number}: brak roku sprawy — pominięto.")
                continue
            records.append(record)
    return records, warnings


def _fold(text) -> str:
    """Małe litery bez polskich znaków i zbędnych spacji — do porównywania nagłówków."""
    normalized = unicodedata.normalize("NFKD", str(text or "").lower().replace("ł", "l"))
    return " ".join("".join(char for char in normalized if not unicodedata.combining(char)).split())


def _map_columns(cells: tuple) -> dict[str, int]:
    columns: dict[str, int] = {}
    headers = [_fold(cell) for cell in cells]
    for field, patterns in COLUMN_PATTERNS:
        for index, header in enumerate(headers):
            if header and index not in columns.values() and any(re.search(pattern, header) for pattern in patterns):
                columns[field] = index
                break
    return columns


def _find_header(rows: list[tuple]) -> tuple[int, dict[str, int]] | None:
    for index, row in enumerate(rows[:HEADER_SEARCH_ROWS]):
        columns = _map_columns(row)
        if "subject" in columns and ("received_date" in columns or "case_number" in columns):
            return index, columns
    return None


def _cell_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def _parse_row(row: tuple, columns: dict[str, int], known_departments: set[str], sheet_title: str, row_number: int) -> dict | None:
    def cell(field: str):
        index = columns.get(field)
        return row[index] if index is not None and index < len(row) else None

    subject = _cell_text(cell("subject"))
    case_number = _cell_text(cell("case_number"))
    if not subject and not case_number:
        return None

    received, received_warning = deadlines.parse_date(cell("received_date"))
    deadline, deadline_warning = deadlines.parse_date(cell("deadline_date"))
    response, response_warning = deadlines.parse_date(cell("response_date"))
    row_warnings = [
        f"{label}: {warning}"
        for label, warning in (("data wpływu", received_warning), ("termin", deadline_warning), ("data odpowiedzi", response_warning))
        if warning
    ]
    if received and not deadline:
        deadline = deadlines.default_deadline(received)
    row_warnings += _consistency_warnings(received, deadline, response)

    # Tekst w komórce terminu (np. „19.08.2026/18.09.2026 - doprecyzowanie wniosku”) to adnotacja o toku sprawy.
    deadline_cell = cell("deadline_date")
    deadline_note = ""
    if isinstance(deadline_cell, str) and not deadline_cell.startswith("="):
        deadline_note = re.sub(r"[\d./\s-]+", " ", deadline_cell).strip(" -")

    departments = _departments(_cell_text(cell("departments")), known_departments)
    status_text = " ".join([_cell_text(cell("status")), _cell_text(cell("notes")), deadline_note]).lower()
    mode_text = f"{_cell_text(cell('procedure_mode'))} {status_text}".lower()
    ordinal = _cell_text(cell("ordinal"))
    return {
        "case_number": case_number or f"(bez numeru) {sheet_title}/{row_number}",
        "year": _year(case_number, received, sheet_title),
        "ordinal": int(ordinal) if ordinal.isdigit() else None,
        "applicant": _cell_text(cell("applicant")),
        "subject": subject,
        "received_date": received.isoformat() if received else None,
        "deadline_date": deadline.isoformat() if deadline else None,
        "response_date": response.isoformat() if response else None,
        "date_parse_warning": "; ".join(row_warnings) or None,
        "status": _status(status_text, bool(response), bool(departments)),
        "procedure_mode": next((mode for key, mode in PROCEDURE_MODE_KEYWORDS.items() if key in mode_text), ProcedureMode.zwykla),
        "departments": departments,
        "initials": _cell_text(cell("initials")) or None,
        "notes": "; ".join(note for note in (_cell_text(cell("notes")), deadline_note) if note) or None,
        "response_text": _cell_text(cell("response_text")) or None,
    }


def _consistency_warnings(received, deadline, response) -> list[str]:
    """Rejestr UMB zawiera np. termin z innym rokiem niż wpływ albo odpowiedź sprzed wpływu."""
    warnings = []
    if received and deadline and deadline < received:
        warnings.append(f"termin {deadline.isoformat()} jest wcześniejszy niż data wpływu {received.isoformat()} — sprawdź rok")
    if received and response and response < received:
        warnings.append(f"data odpowiedzi {response.isoformat()} jest wcześniejsza niż data wpływu {received.isoformat()}")
    if response and deadline and response > deadline and deadline >= (received or deadline):
        warnings.append(f"odpowiedź udzielona {(response - deadline).days} dni po terminie")
    return warnings


def _departments(raw: str, known_departments: set[str]) -> list[str]:
    found: list[str] = []
    for token in re.split(r"[,;/\n]+|\s+", raw.upper()):
        token = token.strip(" .()")
        if token in known_departments and token not in found:
            found.append(token)
    return found


def _status(status_text: str, answered: bool, has_departments: bool) -> CaseStatus:
    if answered:
        return CaseStatus.odpowiedz_wyslana
    for status, keywords in STATUS_KEYWORDS:
        if any(keyword in status_text for keyword in keywords):
            return status
    return CaseStatus.zapytania_wyslane if has_departments else CaseStatus.brak_dzialan


def _year(case_number: str, received, sheet_title: str) -> int | None:
    if year := year_from_case_number(case_number):
        return year
    if received:
        return received.year
    match = re.search(r"20\d{2}", sheet_title or "")
    return int(match.group(0)) if match else None
