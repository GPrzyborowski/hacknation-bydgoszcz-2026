"""Import rejestru spraw z arkusza .xlsx (np. „WNIOSKI O UDOSTĘPNIANIE INFORMACJI PUBLICZNEJ.xlsx”).

Kolumny rozpoznawane są po nagłówkach (bez względu na kolejność); wiersz nagłówka jest wyszukiwany
w pierwszych 15 wierszach każdego arkusza. Daty z dopiskami są parsowane z ostrzeżeniem (date_parse_warning).
"""
import io
import re
import unicodedata

from services.deadlines import default_deadline, parse_date

# Kolejność ma znaczenie: bardziej szczegółowe wzorce przed ogólnymi.
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

PROCEDURE_MODES = {
    "bip": "bip",
    "przetworz": "przetworzona",
    "odmow": "odmowa",
    "dysponent": "nie_dysponent",
    "nie posiada": "nie_dysponent",
}

STATUS_KEYWORDS = [
    ("odpowiedz_wyslana", ["wysłan", "udzielon", "zakończ", "zalatw", "załatw"]),
    ("przygotowana_odpowiedz", ["przygotowan"]),
    ("odpowiedz_w_przygotowaniu", ["w przygotowaniu", "w trakcie"]),
    ("kwerenda", ["kwerend", "przedłuż"]),
    ("doprecyzowanie", ["doprecyz", "wezwan", "uzupełn"]),
    ("zapytania_wyslane", ["zapytan", "przekazan", "wydział"]),
]


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text or "").lower().replace("ł", "l"))
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).split())


def _map_header(cells: list) -> dict[str, int]:
    mapping: dict[str, int] = {}
    folded = [_fold(c) for c in cells]
    for field, patterns in COLUMN_PATTERNS:
        for idx, header in enumerate(folded):
            if not header or idx in mapping.values():
                continue
            if any(re.search(p, header) for p in patterns):
                mapping[field] = idx
                break
    return mapping


def _cell_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def _year_from(case_number: str, received, sheet_title: str) -> int | None:
    m = re.search(r"(20\d{2})\s*$", case_number or "")
    if m:
        return int(m.group(1))
    if received:
        return received.year
    m = re.search(r"20\d{2}", sheet_title or "")
    return int(m.group(0)) if m else None


def parse_workbook(data: bytes, known_departments: set[str]) -> tuple[list[dict], list[str]]:
    from openpyxl import load_workbook

    try:
        wb = load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    except Exception as exc:
        raise ValueError("Nie udało się otworzyć pliku .xlsx.") from exc

    records: list[dict] = []
    warnings: list[str] = []
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        header_idx, mapping = None, {}
        for i, row in enumerate(rows[:15]):
            candidate = _map_header(list(row))
            if "subject" in candidate and ("received_date" in candidate or "case_number" in candidate):
                header_idx, mapping = i, candidate
                break
        if header_idx is None:
            warnings.append(f"Arkusz „{ws.title}”: nie znaleziono wiersza nagłówka — pominięto.")
            continue

        for n, row in enumerate(rows[header_idx + 1 :], start=header_idx + 2):
            get = lambda f: row[mapping[f]] if f in mapping and mapping[f] < len(row) else None  # noqa: E731
            subject = _cell_text(get("subject"))
            case_number = _cell_text(get("case_number"))
            if not subject and not case_number:
                continue

            row_warnings = []
            received, w1 = parse_date(get("received_date"))
            deadline, w2 = parse_date(get("deadline_date"))
            response, w3 = parse_date(get("response_date"))
            for label, w in (("data wpływu", w1), ("termin", w2), ("data odpowiedzi", w3)):
                if w:
                    row_warnings.append(f"{label}: {w}")
            if received and not deadline:
                deadline = default_deadline(received)
            # Kontrola spójności — rejestr UMB zawiera np. termin z innym rokiem niż wpływ
            # albo datę odpowiedzi wcześniejszą niż wpływ. Nie poprawiamy po cichu, tylko ostrzegamy.
            if received and deadline and deadline < received:
                row_warnings.append(f"termin {deadline.isoformat()} jest wcześniejszy niż data wpływu {received.isoformat()} — sprawdź rok")
            if received and response and response < received:
                row_warnings.append(f"data odpowiedzi {response.isoformat()} jest wcześniejsza niż data wpływu {received.isoformat()}")
            if response and deadline and response > deadline and deadline >= (received or deadline):
                row_warnings.append(f"odpowiedź udzielona {(response - deadline).days} dni po terminie")

            # Tekst wpisany w komórce terminu (np. „19.08.2026/18.09.2026 - doprecyzowanie wniosku”) to adnotacja o toku sprawy.
            deadline_raw = get("deadline_date")
            deadline_note = ""
            if isinstance(deadline_raw, str) and not deadline_raw.startswith("="):
                deadline_note = re.sub(r"[\d./\s-]+", " ", deadline_raw).strip(" -")

            raw_depts = _cell_text(get("departments"))
            departments = []
            for token in re.split(r"[,;/\n]+|\s+", raw_depts.upper()):
                token = token.strip(" .()")
                if token and token in known_departments and token not in departments:
                    departments.append(token)

            status_text = " ".join([_cell_text(get("status")), _cell_text(get("notes")), deadline_note]).lower()
            status = "odpowiedz_wyslana" if response else None
            if not status:
                for code, kws in STATUS_KEYWORDS:
                    if any(k in status_text for k in kws):
                        status = code
                        break
            status = status or ("zapytania_wyslane" if departments else "brak_dzialan")

            mode_text = (_cell_text(get("procedure_mode")) + " " + status_text).lower()
            procedure_mode = next((v for k, v in PROCEDURE_MODES.items() if k in mode_text), "zwykla")

            year = _year_from(case_number, received, ws.title)
            if year is None:
                warnings.append(f"Arkusz „{ws.title}”, wiersz {n}: brak roku sprawy — pominięto.")
                continue
            ordinal_text = _cell_text(get("ordinal"))
            records.append(
                {
                    "case_number": case_number or f"(bez numeru) {ws.title}/{n}",
                    "year": year,
                    "ordinal": int(ordinal_text) if ordinal_text.isdigit() else None,
                    "applicant": _cell_text(get("applicant")),
                    "subject": subject,
                    "received_date": received.isoformat() if received else None,
                    "deadline_date": deadline.isoformat() if deadline else None,
                    "response_date": response.isoformat() if response else None,
                    "date_parse_warning": "; ".join(row_warnings) or None,
                    "status": status,
                    "procedure_mode": procedure_mode,
                    "departments": departments,
                    "initials": _cell_text(get("initials")) or None,
                    "notes": "; ".join(x for x in (_cell_text(get("notes")), deadline_note) if x) or None,
                    "response_text": _cell_text(get("response_text")) or None,
                }
            )
    return records, warnings
