"""Ewidencja odpowiedzi wydziałów w sprawie: które odpowiedziały, na które czekamy, gdzie poproszono o uszczegółowienie.

Zarządzenie nr 535/2024 § 10–11: koordynator przekazuje zakres wniosku wydziałom, a wydziały przesyłają projekt
odpowiedzi w wyznaczonym terminie. Tabela case_departments jest jedynym źródłem listy wydziałów sprawy.
"""
import sqlite3
from collections import defaultdict
from datetime import date

from domain import DEPT_STATUS_LABELS, DeptStatus
from errors import Conflict, NotFound


def rows_by_case(conn: sqlite3.Connection, case_ids_sql: str = "SELECT id FROM cases", params: tuple = ()) -> dict[int, list[dict]]:
    """Wiersze ewidencji pogrupowane po sprawach, w kolejności dodania wydziałów."""
    grouped: dict[int, list[dict]] = defaultdict(list)
    query = f"SELECT * FROM case_departments WHERE case_id IN ({case_ids_sql}) ORDER BY rowid"
    for row in conn.execute(query, params):
        grouped[row["case_id"]].append(dict(row))
    return grouped


def rows_for_case(conn: sqlite3.Connection, case_id: int) -> list[dict]:
    return rows_by_case(conn, "?", (case_id,)).get(case_id, [])


def codes(conn: sqlite3.Connection, case_id: int) -> list[str]:
    return [row["code"] for row in rows_for_case(conn, case_id)]


def summarize(rows: list[dict]) -> dict:
    return {
        "dept_total": len(rows),
        "dept_answered": sum(row["status"] == DeptStatus.odpowiedzial for row in rows),
        "dept_waiting": [row["code"] for row in rows if row["status"] == DeptStatus.oczekuje],
        "dept_clarification": [row["code"] for row in rows if row["status"] == DeptStatus.uszczegolowienie],
    }


def describe(rows: list[dict], department_names: dict[str, str]) -> list[dict]:
    return [
        {
            "code": row["code"],
            "name": department_names.get(row["code"], row["code"]),
            "status": row["status"],
            "status_label": DEPT_STATUS_LABELS.get(row["status"], row["status"]),
            "requested_at": row["requested_at"],
            "answered_at": row["answered_at"],
            "clarification_count": row["clarification_count"],
            "note": row["note"],
        }
        for row in rows
    ]


def set_departments(
    conn: sqlite3.Connection,
    case_id: int,
    department_codes: list[str],
    *,
    answered: bool = False,
    requested_at: str | None = None,
    answered_at: str | None = None,
) -> None:
    """Ustawia listę wydziałów sprawy. Wydziały, które zostają, zachowują swój status odpowiedzi."""
    existing = set(codes(conn, case_id))
    for code in department_codes:
        if code not in existing:
            conn.execute(
                "INSERT INTO case_departments(case_id, code, status, requested_at, answered_at)"
                " VALUES (?, ?, ?, coalesce(?, date('now')), ?)",
                (case_id, code, DeptStatus.odpowiedzial if answered else DeptStatus.oczekuje, requested_at,
                 answered_at if answered else None),
            )
    for code in existing - set(department_codes):
        conn.execute("DELETE FROM case_departments WHERE case_id = ? AND code = ?", (case_id, code))


def add(conn: sqlite3.Connection, case_id: int, code: str) -> None:
    if code in codes(conn, case_id):
        raise Conflict(f"Wydział {code} jest już w sprawie.")
    conn.execute("INSERT INTO case_departments(case_id, code) VALUES (?, ?)", (case_id, code))


def remove(conn: sqlite3.Connection, case_id: int, code: str) -> None:
    conn.execute("DELETE FROM case_departments WHERE case_id = ? AND code = ?", (case_id, code))


def mark_answered(conn: sqlite3.Connection, case_id: int, code: str | None) -> str | None:
    """Odnotowuje odpowiedź wydziału. Bez wskazanego wydziału — jeśli czeka tylko jeden, to on odpowiedział."""
    if not code:
        waiting = [row["code"] for row in rows_for_case(conn, case_id) if row["status"] != DeptStatus.odpowiedzial]
        if len(waiting) != 1:
            return None
        code = waiting[0]
    conn.execute("INSERT OR IGNORE INTO case_departments(case_id, code) VALUES (?, ?)", (case_id, code))
    conn.execute(
        "UPDATE case_departments SET status = ?, answered_at = ? WHERE case_id = ? AND code = ?",
        (DeptStatus.odpowiedzial, date.today().isoformat(), case_id, code),
    )
    return code


def set_status(conn: sqlite3.Connection, case_id: int, code: str, status: DeptStatus, note: str | None = None) -> None:
    if code not in codes(conn, case_id):
        raise NotFound(f"Wydziału {code} nie ma w tej sprawie.")
    answered_at = date.today().isoformat() if status == DeptStatus.odpowiedzial else None
    clarification_increment = int(status == DeptStatus.uszczegolowienie)
    conn.execute(
        "UPDATE case_departments SET status = ?, answered_at = ?, note = coalesce(?, note),"
        " clarification_count = clarification_count + ? WHERE case_id = ? AND code = ?",
        (status, answered_at, note, clarification_increment, case_id, code),
    )
