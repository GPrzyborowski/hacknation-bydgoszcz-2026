"""SQLite z indeksami pełnotekstowymi FTS5 (cases_fts, rules_fts)."""
import json
import sqlite3
from contextlib import contextmanager
from typing import Iterator

import config
import seed_data

SCHEMA = """
CREATE TABLE IF NOT EXISTS departments (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    keywords TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1
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
    departments TEXT NOT NULL DEFAULT '[]',
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

CREATE TABLE IF NOT EXISTS case_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    event TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS department_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    department TEXT,
    filename TEXT,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS response_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    draft_text TEXT NOT NULL,
    anonymization_candidates TEXT NOT NULL DEFAULT '[]',
    final_text TEXT,
    generated_format TEXT,
    kind TEXT NOT NULL DEFAULT 'odpowiedz',
    llm_used INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
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

CREATE TABLE IF NOT EXISTS external_entities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    name_genitive TEXT NOT NULL,
    contact TEXT NOT NULL DEFAULT '',
    keywords TEXT NOT NULL DEFAULT '',
    is_active INTEGER NOT NULL DEFAULT 1
);

-- Dokumenty sprawy: wniosek, pisma (kwerenda, doprecyzowanie), odpowiedź — tekst do podglądu i wyszukiwania.
CREATE TABLE IF NOT EXISTS case_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    filename TEXT,
    text TEXT NOT NULL,
    document_date TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS anonymization_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    legal_basis TEXT NOT NULL DEFAULT '',
    regex TEXT,
    mask TEXT NOT NULL DEFAULT '[ANONIMIZACJA]',
    is_active INTEGER NOT NULL DEFAULT 1
);
"""

FTS_SCHEMA = """
CREATE VIRTUAL TABLE IF NOT EXISTS cases_fts USING fts5(
    case_number, applicant, subject, response_text, departments,
    tokenize = 'unicode61 remove_diacritics 2'
);
CREATE VIRTUAL TABLE IF NOT EXISTS rules_fts USING fts5(
    title, source, content,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""

FTS_ENABLED = False


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
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
    """Zależność FastAPI — jedno połączenie na żądanie, commit na końcu."""
    with get_conn() as conn:
        yield conn


def init_db() -> None:
    global FTS_ENABLED
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)
        try:
            conn.executescript(FTS_SCHEMA)
            FTS_ENABLED = True
        except sqlite3.OperationalError:
            # SQLite bez FTS5 — wyszukiwanie przechodzi na LIKE (wolniej, ale działa).
            FTS_ENABLED = False
        _seed(conn)
        if config.SEED_DEMO_DATA:
            import demo_seed

            demo_seed.load_if_empty(conn)
        refresh_derived(conn)
        if FTS_ENABLED:
            _rebuild_fts_if_needed(conn)


def refresh_derived(conn: sqlite3.Connection) -> None:
    """Uzupełnia dane pochodne po imporcie: ewidencję wydziałów i pierwotny termin 14-dniowy."""
    from services import dept_tracking

    dept_tracking.backfill(conn)
    conn.execute(
        "UPDATE cases SET original_deadline_date = date(received_date, '+14 days') "
        "WHERE original_deadline_date IS NULL AND received_date IS NOT NULL"
    )


def _migrate(conn: sqlite3.Connection) -> None:
    """Dodaje kolumny, których nie było w starszych wersjach bazy (CREATE IF NOT EXISTS ich nie doda)."""
    case_columns = {r[1] for r in conn.execute("PRAGMA table_info(cases)")}
    if "original_deadline_date" not in case_columns:
        # Pierwotny termin 14-dniowy — do wyliczenia przedłużenia (kwerenda +N dni) i kontroli art. 13 ust. 2.
        conn.execute("ALTER TABLE cases ADD COLUMN original_deadline_date TEXT")
    # Status odpowiedzi każdego wydziału w sprawie: oczekuje / odpowiedzial / uszczegolowienie.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS case_departments (
            case_id INTEGER NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
            code TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'oczekuje',
            requested_at TEXT NOT NULL DEFAULT (date('now')),
            answered_at TEXT,
            clarification_count INTEGER NOT NULL DEFAULT 0,
            note TEXT,
            PRIMARY KEY (case_id, code)
        )
        """
    )
    columns = {r[1] for r in conn.execute("PRAGMA table_info(response_drafts)")}
    if "kind" not in columns:
        conn.execute("ALTER TABLE response_drafts ADD COLUMN kind TEXT NOT NULL DEFAULT 'odpowiedz'")


def _seed(conn: sqlite3.Connection) -> None:
    if not conn.execute("SELECT 1 FROM departments LIMIT 1").fetchone():
        conn.executemany("INSERT INTO departments(code, name, keywords) VALUES (?, ?, ?)", seed_data.DEPARTMENTS)
    if not conn.execute("SELECT 1 FROM anonymization_categories LIMIT 1").fetchone():
        conn.executemany(
            "INSERT INTO anonymization_categories(name, legal_basis, regex, mask) VALUES (?, ?, ?, ?)",
            seed_data.ANONYMIZATION_CATEGORIES,
        )
    if not conn.execute("SELECT 1 FROM external_entities LIMIT 1").fetchone():
        conn.executemany(
            "INSERT INTO external_entities(name, name_genitive, contact, keywords) VALUES (?, ?, ?, ?)",
            seed_data.EXTERNAL_ENTITIES,
        )
    if not conn.execute("SELECT 1 FROM rules LIMIT 1").fetchone():
        for title, source, content in seed_data.RULES:
            cur = conn.execute("INSERT INTO rules(title, source, content) VALUES (?, ?, ?)", (title, source, content))
            if FTS_ENABLED:
                index_rule(conn, cur.lastrowid)


def _rebuild_fts_if_needed(conn: sqlite3.Connection) -> None:
    n_cases = conn.execute("SELECT COUNT(*) FROM cases").fetchone()[0]
    n_fts = conn.execute("SELECT COUNT(*) FROM cases_fts").fetchone()[0]
    if n_cases != n_fts:
        conn.execute("DELETE FROM cases_fts")
        for (case_id,) in conn.execute("SELECT id FROM cases").fetchall():
            index_case(conn, case_id)


# --- utrzymanie indeksów -------------------------------------------------------------------

def index_case(conn: sqlite3.Connection, case_id: int) -> None:
    if not FTS_ENABLED:
        return
    row = conn.execute(
        "SELECT case_number, applicant, subject, response_text, departments, request_text FROM cases WHERE id = ?",
        (case_id,),
    ).fetchone()
    conn.execute("DELETE FROM cases_fts WHERE rowid = ?", (case_id,))
    if row is None:
        return
    depts = " ".join(json.loads(row["departments"] or "[]"))
    # Treść wniosku (jeśli jest) dokładamy do tematu, żeby podobieństwo działało też po pełnym tekście.
    subject = row["subject"] or ""
    if row["request_text"]:
        subject = f"{subject}\n{row['request_text'][:4000]}"
    conn.execute(
        "INSERT INTO cases_fts(rowid, case_number, applicant, subject, response_text, departments) VALUES (?, ?, ?, ?, ?, ?)",
        (case_id, row["case_number"], row["applicant"] or "", subject, row["response_text"] or "", depts),
    )


def index_rule(conn: sqlite3.Connection, rule_id: int) -> None:
    if not FTS_ENABLED:
        return
    conn.execute("DELETE FROM rules_fts WHERE rowid = ?", (rule_id,))
    row = conn.execute("SELECT title, source, content, is_active FROM rules WHERE id = ?", (rule_id,)).fetchone()
    if row is None or not row["is_active"]:
        return
    conn.execute(
        "INSERT INTO rules_fts(rowid, title, source, content) VALUES (?, ?, ?, ?)",
        (rule_id, row["title"], row["source"], row["content"]),
    )


def log_event(conn: sqlite3.Connection, case_id: int, event: str, detail: str | None = None) -> None:
    conn.execute("INSERT INTO case_events(case_id, event, detail) VALUES (?, ?, ?)", (case_id, event, detail))
