"""Tok sprawy: rejestracja, korekta danych, zmiany statusu, wydziały oraz dopisywanie spraw do archiwum."""
import sqlite3
from datetime import date

import db
from domain import CaseStatus, DeptStatus, DocumentKind, initial_status
from errors import BadRequest, Conflict, NotFound
from schemas import ManualCase, RegisterCase, StatusUpdate, UpdateCase
from services import case_store, case_views, deadlines, departments, dept_tracking, drafting

ARCHIVE_SOURCE = "archiwum"
EXCEL_SOURCE = "excel"


def register(conn: sqlite3.Connection, data: RegisterCase) -> dict:
    """Rejestruje wniosek po weryfikacji danych przez urzędnika. Prośby do wydziałów to tylko propozycje treści."""
    year = data.year or data.received_date.year
    codes = departments.validate(conn, data.departments)
    case_number = (data.case_number or "").strip() or case_store.next_case_number(conn, year)
    if case_store.find_id(conn, case_number) is not None:
        raise Conflict(f"Sprawa o znaku {case_number} już istnieje.")

    parsed = data.parsed_request.model_dump() if data.parsed_request else None
    intake = None
    if data.intake_id is not None:
        intake = conn.execute("SELECT * FROM intakes WHERE id = ?", (data.intake_id,)).fetchone()
        if intake is None:
            raise NotFound(f"Nie znaleziono analizy wniosku (intake_id={data.intake_id}).")
        parsed = parsed or db.from_json(intake["parsed_json"], None)

    deadline = data.deadline_date or deadlines.default_deadline(data.received_date)
    status = initial_status(codes)
    case_id = case_store.insert(
        conn,
        {
            "case_number": case_number,
            "year": year,
            "ordinal": case_store.next_ordinal(conn, year),
            "applicant": data.applicant,
            "applicant_contact": data.applicant_contact,
            "subject": data.subject,
            "received_date": data.received_date.isoformat(),
            "deadline_date": deadline.isoformat(),
            "status": status,
            "procedure_mode": data.procedure_mode,
            "initials": data.initials,
            "notes": data.notes,
            "request_text": intake["text"] if intake else None,
            "parsed_request": db.to_json(parsed) if parsed else None,
            "intake_id": data.intake_id,
        },
    )
    dept_tracking.set_departments(conn, case_id, codes)
    if intake and intake["text"]:
        case_store.add_document(
            conn, case_id, DocumentKind.wniosek, intake["text"],
            filename=intake["filename"], document_date=data.received_date.isoformat(),
        )
    case_store.log_event(conn, case_id, "rejestracja", f"status: {status}")

    templates = {}
    if data.generate_dept_request_template and codes:
        case = {"case_number": case_number, "received_date": data.received_date.isoformat(), "subject": data.subject}
        templates = drafting.department_requests(conn, case, codes, (parsed or {}).get("pytania") or [], deadline)
    return {
        "id": case_id,
        "case_number": case_number,
        "status": status,
        "deadline_date": deadline.isoformat(),
        "departments": codes,
        "request_templates": templates,
    }


def update_details(conn: sqlite3.Connection, case_id: int, data: UpdateCase) -> dict:
    case_store.get(conn, case_id)
    changes = data.model_dump(exclude_unset=True)
    if not changes:
        raise BadRequest("Brak pól do zmiany.")
    codes = departments.validate(conn, changes["departments"] or []) if "departments" in changes else None
    columns = {key: value.isoformat() if isinstance(value, date) else value for key, value in changes.items() if key != "departments"}
    if columns.get("received_date"):
        columns["year"] = int(columns["received_date"][:4])

    if columns:
        case_store.update(conn, case_id, columns)
    else:
        case_store.touch(conn, case_id)
    if codes is not None:
        dept_tracking.set_departments(conn, case_id, codes)
    case_store.log_event(conn, case_id, "edycja", ", ".join([*changes, *(["year"] if "year" in columns else [])]))
    return case_views.item(conn, case_id)


def change_status(conn: sqlite3.Connection, case_id: int, data: StatusUpdate) -> dict:
    """Ręczna zmiana statusu. Kwerenda bez podanego terminu dostaje termin maksymalny (2 miesiące, art. 13 ust. 2)."""
    row = case_store.get(conn, case_id)
    received = deadlines.from_iso(row["received_date"])
    deadline = data.deadline_date
    if data.status == CaseStatus.kwerenda and deadline is None and received:
        deadline = deadlines.extended_deadline(received)
    deadlines.ensure_within_extension_limit(received, deadline)

    response_date = row["response_date"]
    if data.status == CaseStatus.odpowiedz_wyslana and not response_date:
        response_date = deadlines.today().isoformat()
    detail = str(data.status) + (f", termin {deadline.isoformat()}" if deadline else "") + (f" — {data.note}" if data.note else "")
    case_store.set_status(conn, case_id, data.status, deadline=deadline, response_date=response_date, event="status", detail=detail)

    item = case_views.item(conn, case_id)
    return {"case_id": case_id, "status": data.status, "deadline_date": item["deadline_date"], "days_remaining": item["days_remaining"]}


# --- wydziały w sprawie ------------------------------------------------------------------------------

def department_statuses(conn: sqlite3.Connection, case_id: int) -> list[dict]:
    return dept_tracking.describe(dept_tracking.rows_for_case(conn, case_id), departments.names(conn))


def add_department(conn: sqlite3.Connection, case_id: int, code: str) -> list[dict]:
    """Zapytanie kolejnego wydziału; sprawa bez działań przechodzi w status „zapytania wysłane”."""
    row = case_store.get(conn, case_id)
    code = departments.validate_one(conn, code)
    dept_tracking.add(conn, case_id, code)
    if row["status"] == CaseStatus.brak_dzialan:
        case_store.set_status(conn, case_id, CaseStatus.zapytania_wyslane)
    else:
        case_store.touch(conn, case_id)
    case_store.log_event(conn, case_id, "zapytanie_do_wydzialu", code)
    return department_statuses(conn, case_id)


def set_department_status(conn: sqlite3.Connection, case_id: int, code: str, status: DeptStatus, note: str | None) -> list[dict]:
    case_store.get(conn, case_id)
    code = code.upper()
    dept_tracking.set_status(conn, case_id, code, status, note)
    case_store.log_event(conn, case_id, f"wydzial_{status}", code)
    return department_statuses(conn, case_id)


def remove_department(conn: sqlite3.Connection, case_id: int, code: str) -> list[dict]:
    case_store.get(conn, case_id)
    dept_tracking.remove(conn, case_id, code.upper())
    return department_statuses(conn, case_id)


# --- archiwum -----------------------------------------------------------------------------------------

def add_archived_case(conn: sqlite3.Connection, data: ManualCase) -> dict:
    """Wzorcowa sprawa z udzieloną odpowiedzią — zasila wyszukiwanie podobnych spraw."""
    year = data.year or (data.received_date.year if data.received_date else None) or case_store.year_from_case_number(data.case_number)
    if year is None:
        raise BadRequest("Podaj rok sprawy lub datę wpływu.")
    codes = departments.validate(conn, data.departments)
    answered = bool(data.response_date or data.response_text)
    record = {
        "case_number": data.case_number,
        "year": year,
        "applicant": data.applicant,
        "subject": data.subject,
        "received_date": data.received_date.isoformat() if data.received_date else None,
        "response_date": data.response_date.isoformat() if data.response_date else None,
        "status": CaseStatus.odpowiedz_wyslana if answered else CaseStatus.brak_dzialan,
        "procedure_mode": data.procedure_mode,
        "request_text": data.request_text,
        "response_text": data.response_text,
        "source": ARCHIVE_SOURCE,
    }
    case_id = case_store.insert(conn, record)
    case_store.set_archived_departments(conn, case_id, record, codes)
    return {"id": case_id, "case_number": data.case_number}


def import_records(conn: sqlite3.Connection, records: list[dict], update_existing: bool) -> dict:
    """Zapis spraw z arkusza: nowe są dodawane, istniejące (ten sam znak sprawy) — aktualizowane albo pomijane."""
    imported = updated = skipped = 0
    for record in records:
        codes = record.pop("departments")
        case_id = case_store.find_id(conn, record["case_number"])
        if case_id is None:
            case_id = case_store.insert(conn, {**record, "source": EXCEL_SOURCE})
            imported += 1
        elif update_existing:
            case_store.update(conn, case_id, record)
            updated += 1
        else:
            skipped += 1
            continue
        case_store.set_archived_departments(conn, case_id, record, codes)
    return {"imported": imported, "updated": updated, "skipped": skipped}
