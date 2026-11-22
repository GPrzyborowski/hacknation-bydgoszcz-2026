"""SQLite: połączenia, schemat i migracje.

Indeksy pełnotekstowe FTS5 (cases_fts, rules_fts) utrzymują triggery, więc kod aplikacji nigdy ich nie aktualizuje.
"""
import json
import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date

import config
from domain import CaseStatus, DeptStatus
from errors import BadRequest

log = logging.getLogger(__name__)

SCHEMA_VERSION = 2

SCHEMA = """
CREATE TABLE IF NOT EXISTS departments (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    keywords TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS external_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    name_genitive TEXT NOT NULL,
    contact TEXT NOT NULL DEFAULT '',
    keywords TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS anonymization_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    legal_basis TEXT NOT NULL DEFAULT '',
    regex TEXT,
    mask TEXT NOT NULL DEFAULT '[ANONIMIZACJA]',
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS intakes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    text TEXT NOT NULL,
    parsed_json TEXT,
    received_date TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_number TEXT NOT NULL,
    year INTEGER NOT NULL,
    ordinal INTEGER,
    applicant TEXT NOT NULL DEFAULT '',
    applicant_contact TEXT,
    subject TEXT NOT NULL DEFAULT '',
    received_date TEXT,
    deadline_date TEXT,
    response_date TEXT,
    date_parse_warning TEXT,
    status TEXT NOT NULL DEFAULT 'brak_dzialan',
    procedure_mode TEXT NOT NULL DEFAULT 'zwykla',
    initials TEXT,
    notes TEXT,
    request_text TEXT,
    parsed_request TEXT,
    response_text TEXT,
    intake_id INTEGER REFERENCES intakes(id),
    source TEXT NOT NULL DEFAULT 'ui',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_cases_year ON cases(year);
CREATE INDEX IF NOT EXISTS idx_cases_received ON cases(received_date);
CREATE INDEX IF NOT EXISTS idx_cases_case_number ON cases(case_number);

-- Wydziały zapytane w sprawie i stan ich odpowiedzi (jedyne źródło listy wydziałów sprawy).
CREATE TABLE IF NOT EXISTS case_departments (
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    code TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'oczekuje',
    requested_at TEXT NOT NULL DEFAULT (date('now')),
    answered_at TEXT,
    clarification_count INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    PRIMARY KEY (case_id, code)
);

CREATE TABLE IF NOT EXISTS case_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    event TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_case_events_case ON case_events(case_id);

CREATE TABLE IF NOT EXISTS case_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    filename TEXT,
    text TEXT NOT NULL,
    document_date TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_case_documents_case ON case_documents(case_id);

CREATE TABLE IF NOT EXISTS department_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    department TEXT,
    filename TEXT,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_department_replies_case ON department_replies(case_id);

CREATE TABLE IF NOT EXISTS response_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    kind TEXT NOT NULL DEFAULT 'odpowiedz',
    draft_text TEXT NOT NULL,
    anonymization_candidates TEXT NOT NULL DEFAULT '[]',
    final_text TEXT,
    generated_format TEXT,
    llm_used INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_response_drafts_case ON response_drafts(case_id);
"""

# Dokument wyszukiwania sprawy: temat z początkiem treści wniosku (podobieństwo po pełnym tekście)
# oraz symbole zapytanych wydziałów. Triggery przepisują go do cases_fts przy każdej zmianie.
SEARCH_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS cases_fts USING fts5(
    case_number, applicant, subject, response_text, departments,
    tokenize = 'unicode61 remove_diacritics 2'
);
CREATE VIRTUAL TABLE IF NOT EXISTS rules_fts USING fts5(
    title, source, content,
    tokenize = 'unicode61 remove_diacritics 2'
);

CREATE VIEW IF NOT EXISTS case_search_documents AS
SELECT
    c.id AS case_id,
    c.case_number,
    c.applicant,
    c.subject || CASE WHEN coalesce(c.request_text, '') = '' THEN ''
                      ELSE char(10) || substr(c.request_text, 1, 4000) END AS subject,
    coalesce(c.response_text, '') AS response_text,
    coalesce((SELECT group_concat(d.code, ' ') FROM case_departments d WHERE d.case_id = c.id), '') AS departments
FROM cases c;

CREATE TRIGGER IF NOT EXISTS cases_fts_after_insert AFTER INSERT ON cases BEGIN
    INSERT INTO cases_fts(rowid, case_number, applicant, subject, response_text, departments)
    SELECT case_id, case_number, applicant, subject, response_text, departments
    FROM case_search_documents WHERE case_id = new.id;
END;

CREATE TRIGGER IF NOT EXISTS cases_fts_after_update
AFTER UPDATE OF case_number, applicant, subject, request_text, response_text ON cases BEGIN
    DELETE FROM cases_fts WHERE rowid = old.id;
    INSERT INTO cases_fts(rowid, case_number, applicant, subject, response_text, departments)
    SELECT case_id, case_number, applicant, subject, response_text, departments
    FROM case_search_documents WHERE case_id = new.id;
END;

CREATE TRIGGER IF NOT EXISTS cases_fts_after_delete AFTER DELETE ON cases BEGIN
    DELETE FROM cases_fts WHERE rowid = old.id;
END;

CREATE TRIGGER IF NOT EXISTS case_departments_fts_after_insert AFTER INSERT ON case_departments BEGIN
    UPDATE cases_fts SET departments = (SELECT departments FROM case_search_documents WHERE case_id = new.case_id)
    WHERE rowid = new.case_id;
END;

CREATE TRIGGER IF NOT EXISTS case_departments_fts_after_delete AFTER DELETE ON case_departments BEGIN
    UPDATE cases_fts SET departments = (SELECT departments FROM case_search_documents WHERE case_id = old.case_id)
    WHERE rowid = old.case_id;
END;

CREATE TRIGGER IF NOT EXISTS rules_fts_after_insert AFTER INSERT ON rules WHEN new.is_active BEGIN
    INSERT INTO rules_fts(rowid, title, source, content) VALUES (new.id, new.title, new.source, new.content);
END;

CREATE TRIGGER IF NOT EXISTS rules_fts_after_update AFTER UPDATE ON rules BEGIN
    DELETE FROM rules_fts WHERE rowid = old.id;
    INSERT INTO rules_fts(rowid, title, source, content)
    SELECT new.id, new.title, new.source, new.content WHERE new.is_active;
END;

CREATE TRIGGER IF NOT EXISTS rules_fts_after_delete AFTER DELETE ON rules BEGIN
    DELETE FROM rules_fts WHERE rowid = old.id;
END;
"""


def connect() -> sqlite3.Connection:
    # FastAPI otwiera i zamyka zależność w innym wątku puli niż sam endpoint.
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def transaction() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def db_dependency() -> Iterator[sqlite3.Connection]:
    """Zależność FastAPI: jedna transakcja na żądanie, zatwierdzana po udanej odpowiedzi."""
    with transaction() as conn:
        yield conn


# --- migracje ---------------------------------------------------------------------------------

def migrate(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA journal_mode = WAL")
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version == 0 and _table_exists(conn, "cases"):
        version = 1  # baza prototypu sprzed wersjonowania schematu

    conn.executescript(SCHEMA)
    if version == 1:
        _upgrade_prototype(conn)
    _create_search_schema(conn)
    if version < SCHEMA_VERSION:
        rebuild_search_index(conn)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        log.info("Schemat bazy zaktualizowany do wersji %s", SCHEMA_VERSION)


def _create_search_schema(conn: sqlite3.Connection) -> None:
    try:
        conn.executescript(SEARCH_SCHEMA)
    except sqlite3.OperationalError as exc:
        raise RuntimeError(f"SQLite bez modułu FTS5 — wyszukiwanie spraw nie może działać ({exc}).") from exc


def rebuild_search_index(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        DELETE FROM cases_fts;
        INSERT INTO cases_fts(rowid, case_number, applicant, subject, response_text, departments)
        SELECT case_id, case_number, applicant, subject, response_text, departments FROM case_search_documents;
        DELETE FROM rules_fts;
        INSERT INTO rules_fts(rowid, title, source, content) SELECT id, title, source, content FROM rules WHERE is_active;
        """
    )


def _upgrade_prototype(conn: sqlite3.Connection) -> None:
    """Prototyp trzymał wydziały sprawy w kolumnie JSON i zapisywał wyliczany termin 14-dniowy."""
    if "kind" not in _columns(conn, "response_drafts"):
        conn.execute("ALTER TABLE response_drafts ADD COLUMN kind TEXT NOT NULL DEFAULT 'odpowiedz'")

    case_columns = _columns(conn, "cases")
    if "departments" in case_columns:
        _move_departments_to_tracking(conn)
    for obsolete in ("departments", "original_deadline_date"):
        if obsolete in case_columns:
            try:
                conn.execute(f"ALTER TABLE cases DROP COLUMN {obsolete}")
            except sqlite3.OperationalError:
                log.warning("SQLite nie obsługuje DROP COLUMN — kolumna cases.%s zostaje, ale nie jest używana", obsolete)


def _move_departments_to_tracking(conn: sqlite3.Connection) -> None:
    rows = conn.execute("SELECT id, departments, status, received_date, response_date FROM cases").fetchall()
    for row in rows:
        closed = row["status"] in (CaseStatus.odpowiedz_wyslana, CaseStatus.przygotowana_odpowiedz)
        for code in from_json(row["departments"], []):
            conn.execute(
                "INSERT OR IGNORE INTO case_departments(case_id, code, status, requested_at, answered_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    row["id"],
                    code,
                    DeptStatus.odpowiedzial if closed else DeptStatus.oczekuje,
                    row["received_date"] or date.today().isoformat(),
                    row["response_date"] if closed else None,
                ),
            )


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)).fetchone() is not None


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


# --- pomocnicze ---------------------------------------------------------------------------------

def to_json(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def from_json(text: str | None, default):
    return json.loads(text) if text else default


def update_row(conn: sqlite3.Connection, table: str, key_column: str, key, changes: dict, *, touch: bool = False) -> None:
    """UPDATE tylko podanych kolumn. Nazwy kolumn pochodzą z modeli API, nigdy z danych użytkownika."""
    if not changes:
        raise BadRequest("Brak pól do zmiany.")
    assignments = [f"{column} = ?" for column in changes]
    if touch:
        assignments.append("updated_at = datetime('now')")
    conn.execute(f"UPDATE {table} SET {', '.join(assignments)} WHERE {key_column} = ?", (*changes.values(), key))
