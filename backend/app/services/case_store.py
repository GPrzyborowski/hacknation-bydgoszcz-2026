"""Zapis i odczyt spraw: numeracja, statusy, dokumenty, zdarzenia i materiały z wydziałów."""
import re
import sqlite3
from datetime import date

import config
import db
from domain import CaseStatus, DocumentKind
from errors import NotFound
from services import dept_tracking

# Kolumny sprawy, które można ustawić przy rejestracji, imporcie lub edycji.
WRITABLE_COLUMNS = (
    "case_number", "year", "ordinal", "applicant", "applicant_contact", "subject", "received_date", "deadline_date",
    "response_date", "date_parse_warning", "status", "procedure_mode", "initials", "notes", "request_text",
    "parsed_request", "response_text", "intake_id", "source",
)

_YEAR_SUFFIX = re.compile(r"(20\d{2})\s*$")


def get(conn: sqlite3.Connection, case_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    if row is None:
        raise NotFound(f"Nie znaleziono sprawy o id {case_id}.")
    return row


def find_id(conn: sqlite3.Connection, case_number: str) -> int | None:
    row = conn.execute("SELECT id FROM cases WHERE case_number = ?", (case_number,)).fetchone()
    return row["id"] if row else None


def year_from_case_number(case_number: str | None) -> int | None:
    match = _YEAR_SUFFIX.search(case_number or "")
    return int(match.group(1)) if match else None


def next_case_number(conn: sqlite3.Connection, year: int) -> str:
    prefix = f"{config.CASE_NUMBER_PREFIX}."
    highest = 0
    for (number,) in conn.execute("SELECT case_number FROM cases WHERE year = ? AND case_number LIKE ?", (year, f"{prefix}%")):
        sequence = number[len(prefix):].rsplit(".", 1)[0]
        if sequence.isdigit():
            highest = max(highest, int(sequence))
    return f"{prefix}{highest + 1}.{year}"


def next_ordinal(conn: sqlite3.Connection, year: int) -> int:
    return conn.execute("SELECT coalesce(max(ordinal), 0) + 1 FROM cases WHERE year = ?", (year,)).fetchone()[0]


def parsed_request(row: sqlite3.Row) -> dict:
    return db.from_json(row["parsed_request"], {})


def insert(conn: sqlite3.Connection, record: dict) -> int:
    columns = [column for column in WRITABLE_COLUMNS if column in record]
    cursor = conn.execute(
        f"INSERT INTO cases({', '.join(columns)}) VALUES ({', '.join('?' * len(columns))})",
        [record[column] for column in columns],
    )
    return cursor.lastrowid


def update(conn: sqlite3.Connection, case_id: int, changes: dict) -> None:
    db.update_row(conn, "cases", "id", case_id, changes, touch=True)


def touch(conn: sqlite3.Connection, case_id: int) -> None:
    conn.execute("UPDATE cases SET updated_at = datetime('now') WHERE id = ?", (case_id,))


def set_archived_departments(conn: sqlite3.Connection, case_id: int, record: dict, codes: list[str]) -> None:
    """Wydziały sprawy z archiwum lub importu: w sprawie zakończonej wydziały już odpowiedziały."""
    closed = record.get("status") in (CaseStatus.odpowiedz_wyslana, CaseStatus.przygotowana_odpowiedz)
    dept_tracking.set_departments(
        conn, case_id, codes,
        answered=closed, requested_at=record.get("received_date"), answered_at=record.get("response_date"),
    )


def delete(conn: sqlite3.Connection, case_id: int) -> None:
    get(conn, case_id)
    conn.execute("DELETE FROM cases WHERE id = ?", (case_id,))


def set_status(
    conn: sqlite3.Connection,
    case_id: int,
    status: CaseStatus,
    *,
    deadline: date | None = None,
    response_date: str | None = None,
    response_text: str | None = None,
    event: str | None = None,
    detail: str | None = None,
) -> None:
    """Zmiana statusu wraz z opcjonalnym nowym terminem i danymi odpowiedzi, z wpisem w historii sprawy."""
    changes: dict = {"status": status}
    if deadline:
        changes["deadline_date"] = deadline.isoformat()
    if response_date:
        changes["response_date"] = response_date
    if response_text is not None:
        changes["response_text"] = response_text
    update(conn, case_id, changes)
    if event:
        log_event(conn, case_id, event, detail)


def log_event(conn: sqlite3.Connection, case_id: int, event: str, detail: str | None = None) -> None:
    conn.execute("INSERT INTO case_events(case_id, event, detail) VALUES (?, ?, ?)", (case_id, event, detail))


def add_document(
    conn: sqlite3.Connection,
    case_id: int,
    kind: DocumentKind,
    text: str,
    *,
    filename: str | None = None,
    document_date: str | None = None,
) -> None:
    conn.execute(
        "INSERT INTO case_documents(case_id, kind, filename, text, document_date) VALUES (?, ?, ?, ?, ?)",
        (case_id, kind, filename, text, document_date),
    )


def add_reply(conn: sqlite3.Connection, case_id: int, department: str | None, filename: str | None, text: str) -> None:
    conn.execute(
        "INSERT INTO department_replies(case_id, department, filename, text) VALUES (?, ?, ?, ?)",
        (case_id, department, filename, text),
    )


def replies(conn: sqlite3.Connection, case_id: int) -> list[dict]:
    return [
        dict(row)
        for row in conn.execute(
            "SELECT id, department, filename, text, created_at FROM department_replies WHERE case_id = ? ORDER BY id",
            (case_id,),
        )
    ]


def last_reply_text(conn: sqlite3.Connection, case_id: int, department: str) -> str | None:
    row = conn.execute(
        "SELECT text FROM department_replies WHERE case_id = ? AND department = ? ORDER BY id DESC LIMIT 1",
        (case_id, department),
    ).fetchone()
    return row["text"] if row else None
