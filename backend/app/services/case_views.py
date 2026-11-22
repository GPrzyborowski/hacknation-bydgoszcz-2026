"""Sprawy w postaci zwracanej przez API: rejestr z polami wyliczanymi oraz pełna karta sprawy."""
import sqlite3

import db
from domain import CaseStatus
from services import case_store, deadlines, departments, dept_tracking, search

LIST_COLUMNS = (
    "id", "ordinal", "case_number", "year", "applicant", "subject", "received_date", "deadline_date",
    "response_date", "date_parse_warning", "status", "procedure_mode", "initials", "notes",
)


def list_items(
    conn: sqlite3.Connection,
    *,
    year: int | None = None,
    status: CaseStatus | None = None,
    open_only: bool = False,
    query: str | None = None,
) -> list[dict]:
    """Rejestr od najstarszych wniosków (data wpływu, potem kolejność rejestracji)."""
    conditions: list[str] = []
    params: list = []
    if year is not None:
        conditions.append("year = ?")
        params.append(year)
    if status is not None:
        conditions.append("status = ?")
        params.append(status)
    if open_only:
        conditions.append("status != ?")
        params.append(CaseStatus.odpowiedz_wyslana)
    match = search.match_all_words(query) if query else None
    if match:
        conditions.append("id IN (SELECT rowid FROM cases_fts WHERE cases_fts MATCH ?)")
        params.append(match)

    where = " AND ".join(conditions) or "1"
    rows = conn.execute(
        f"SELECT {', '.join(LIST_COLUMNS)} FROM cases WHERE {where} ORDER BY received_date IS NULL, received_date, id",
        params,
    ).fetchall()
    dept_rows = dept_tracking.rows_by_case(conn, f"SELECT id FROM cases WHERE {where}", tuple(params))
    return [_list_item(row, dept_rows.get(row["id"], [])) for row in rows]


def item(conn: sqlite3.Connection, case_id: int) -> dict:
    return _list_item(case_store.get(conn, case_id), dept_tracking.rows_for_case(conn, case_id))


def detail(conn: sqlite3.Connection, case_id: int) -> dict:
    row = case_store.get(conn, case_id)
    dept_rows = dept_tracking.rows_for_case(conn, case_id)
    drafts = conn.execute("SELECT * FROM response_drafts WHERE case_id = ? ORDER BY id DESC", (case_id,))
    documents = conn.execute("SELECT * FROM case_documents WHERE case_id = ? ORDER BY id", (case_id,))
    events = conn.execute("SELECT event, detail, created_at FROM case_events WHERE case_id = ? ORDER BY id", (case_id,))
    return {
        **_list_item(row, dept_rows),
        "applicant_contact": row["applicant_contact"],
        "request_text": row["request_text"],
        "parsed_request": db.from_json(row["parsed_request"], None),
        "response_text": row["response_text"],
        "department_status": dept_tracking.describe(dept_rows, departments.names(conn)),
        "documents": [dict(document) for document in documents],
        "department_replies": case_store.replies(conn, case_id),
        "drafts": [{**dict(draft), "anonymization_candidates": db.from_json(draft["anonymization_candidates"], [])} for draft in drafts],
        "events": [dict(event) for event in events],
    }


def _list_item(row: sqlite3.Row, dept_rows: list[dict]) -> dict:
    received = deadlines.from_iso(row["received_date"])
    deadline = deadlines.from_iso(row["deadline_date"])
    response = deadlines.from_iso(row["response_date"])
    original = deadlines.default_deadline(received) if received else None
    closed = row["status"] == CaseStatus.odpowiedz_wyslana
    return {
        **{column: row[column] for column in LIST_COLUMNS},
        "departments": [dept["code"] for dept in dept_rows],
        **dept_tracking.summarize(dept_rows),
        "original_deadline_date": original.isoformat() if original else None,
        "extension_days": (deadline - original).days if deadline and original and deadline > original else 0,
        "max_deadline_date": deadlines.extended_deadline(received).isoformat() if received else None,
        # Rejestr UMB („Pozostało dni”) pokazuje 0 dla spraw zakończonych.
        "days_remaining": 0 if closed else deadlines.days_remaining(deadline),
        "answered_on_time": response <= deadline if closed and response and deadline else None,
        "deadline_note": None if closed else deadlines.deadline_note(deadline),
        "urgency": deadlines.urgency(deadline, row["status"]),
    }
