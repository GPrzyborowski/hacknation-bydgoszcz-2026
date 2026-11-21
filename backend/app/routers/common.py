"""Wspólne narzędzia routerów: odczyt uploadu, mapowanie wyjątków na kody HTTP, serializacja spraw."""
import json
import sqlite3
from contextlib import contextmanager

from fastapi import HTTPException, UploadFile

import config
from services import deadlines, extraction, llm


def read_upload(file: UploadFile) -> bytes:
    """Synchroniczny odczyt — endpointy są zwykłymi `def` (FastAPI uruchamia je w puli wątków,
    więc długie wywołania LLM/OCR nie blokują pętli zdarzeń)."""
    data = file.file.read(config.MAX_UPLOAD_BYTES + 1)
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"Plik przekracza {config.MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    if not data:
        raise HTTPException(400, "Plik jest pusty.")
    return data


@contextmanager
def http_errors():
    """Zamienia błędy ekstrakcji / LLM na kody z dokumentacji API (400, 403, 422, 502)."""
    try:
        yield
    except extraction.ExtractionError as exc:
        raise HTTPException(400, str(exc)) from exc
    except extraction.OcrUnavailable as exc:
        raise HTTPException(422, str(exc)) from exc
    except llm.LLMForbidden as exc:
        raise HTTPException(403, str(exc)) from exc
    except llm.LLMError as exc:
        raise HTTPException(502, str(exc)) from exc


def get_case_row(conn: sqlite3.Connection, case_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM cases WHERE id = ?", (case_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"Nie znaleziono sprawy o id {case_id}.")
    return row


def case_list_item(row: sqlite3.Row, dept: dict | None = None) -> dict:
    deadline = deadlines.from_iso(row["deadline_date"])
    response = deadlines.from_iso(row["response_date"])
    received = deadlines.from_iso(row["received_date"])
    original = deadlines.from_iso(row["original_deadline_date"]) if "original_deadline_date" in row.keys() else None
    done = row["status"] == "odpowiedz_wyslana"
    dept = dept or {"total": 0, "answered": 0, "waiting": [], "clarification": []}
    extension = (deadline - original).days if deadline and original and deadline > original else 0
    return {
        "original_deadline_date": original.isoformat() if original else None,
        "extension_days": extension,
        "max_deadline_date": deadlines.extended_deadline(received).isoformat() if received else None,
        "dept_total": dept["total"],
        "dept_answered": dept["answered"],
        "dept_waiting": dept["waiting"],
        "dept_clarification": dept["clarification"],
        "id": row["id"],
        "ordinal": row["ordinal"],
        "case_number": row["case_number"],
        "year": row["year"],
        "applicant": row["applicant"],
        "subject": row["subject"],
        "received_date": row["received_date"],
        "deadline_date": row["deadline_date"],
        "response_date": row["response_date"],
        "date_parse_warning": row["date_parse_warning"],
        "status": row["status"],
        "procedure_mode": row["procedure_mode"],
        "departments": json.loads(row["departments"] or "[]"),
        "initials": row["initials"],
        "notes": row["notes"],
        # Rejestr UMB („Pozostało dni”) pokazuje 0 dla spraw zakończonych.
        "days_remaining": 0 if done else deadlines.days_remaining(deadline),
        "answered_on_time": (response <= deadline) if done and response and deadline else None,
        "deadline_note": None if done else deadlines.deadline_note(deadline),
        "urgency": deadlines.urgency(deadline, row["status"]),
    }


def validate_departments(conn: sqlite3.Connection, codes: list[str]) -> list[str]:
    known = {r[0] for r in conn.execute("SELECT code FROM departments")}
    cleaned: list[str] = []
    for code in codes:
        code = code.strip().upper()
        if code not in known:
            raise HTTPException(400, f"Nieznany symbol komórki: {code}. Listę zwraca GET /api/knowledge/departments.")
        if code not in cleaned:
            cleaned.append(code)
    return cleaned
