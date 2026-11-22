"""Słownik komórek organizacyjnych UMB (wydziały i biura)."""
import sqlite3

from errors import BadRequest


def list_all(conn: sqlite3.Connection) -> list[dict]:
    return [dict(row) for row in conn.execute("SELECT * FROM departments ORDER BY code")]


def list_active(conn: sqlite3.Connection) -> list[dict]:
    return [dict(row) for row in conn.execute("SELECT * FROM departments WHERE is_active ORDER BY code")]


def names(conn: sqlite3.Connection) -> dict[str, str]:
    return {row["code"]: row["name"] for row in conn.execute("SELECT code, name FROM departments")}


def validate(conn: sqlite3.Connection, codes: list[str]) -> list[str]:
    """Symbole wielkimi literami, bez powtórzeń; nieznany symbol to błąd urzędnika, nie literówka do pominięcia."""
    known = set(names(conn))
    cleaned: list[str] = []
    for code in (code.strip().upper() for code in codes):
        if code not in known:
            raise BadRequest(f"Nieznany symbol komórki: {code}. Listę zwraca GET /api/knowledge/departments.")
        if code not in cleaned:
            cleaned.append(code)
    return cleaned


def validate_one(conn: sqlite3.Connection, code: str) -> str:
    return validate(conn, [code])[0]
