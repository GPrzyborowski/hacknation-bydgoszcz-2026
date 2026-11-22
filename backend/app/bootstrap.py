"""Przygotowanie bazy przy starcie: migracje, dane słownikowe i — gdy włączone — dane testowe UMB.

Dane testowe (seed/umb_demo.json) buduje skrypt backend/scripts/build_demo_seed.py z materiałów wyzwania:
10 spraw z rejestru UMB z treścią wniosków, odpowiedzi i pism oraz Zarządzenie nr 535/2024.
"""
import json
import logging
import sqlite3

import config
import db
import seed_data
from domain import CaseStatus, ProcedureMode
from services import case_store

log = logging.getLogger(__name__)

DEMO_SOURCE = "dane_testowe_umb"


def init_database() -> None:
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with db.transaction() as conn:
        db.migrate(conn)
        _seed_reference_data(conn)
        if config.SEED_DEMO_DATA:
            _load_demo_data(conn)


def _is_empty(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone() is None


def _seed_reference_data(conn: sqlite3.Connection) -> None:
    seeds = [
        ("departments", "INSERT INTO departments(code, name, keywords) VALUES (?, ?, ?)", seed_data.DEPARTMENTS),
        (
            "anonymization_categories",
            "INSERT INTO anonymization_categories(name, legal_basis, regex, mask) VALUES (?, ?, ?, ?)",
            seed_data.ANONYMIZATION_CATEGORIES,
        ),
        (
            "external_entities",
            "INSERT INTO external_entities(name, name_genitive, contact, keywords) VALUES (?, ?, ?, ?)",
            seed_data.EXTERNAL_ENTITIES,
        ),
        ("rules", "INSERT INTO rules(title, source, content) VALUES (?, ?, ?)", seed_data.RULES),
    ]
    for table, insert, rows in seeds:
        if _is_empty(conn, table):
            conn.executemany(insert, rows)


def _load_demo_data(conn: sqlite3.Connection) -> None:
    if not config.SEED_FILE.exists():
        return
    data = json.loads(config.SEED_FILE.read_text(encoding="utf-8"))

    if _is_empty(conn, "cases"):
        cases = data.get("cases", [])
        for case in cases:
            _insert_demo_case(conn, case)
        log.info("Wczytano sprawy testowe UMB: %s", len(cases))

    existing_rules = {(row["title"], row["source"]) for row in conn.execute("SELECT title, source FROM rules")}
    conn.executemany(
        "INSERT INTO rules(title, source, content) VALUES (?, ?, ?)",
        [
            (rule["title"], rule["source"], rule["content"])
            for rule in data.get("rules", [])
            if (rule["title"], rule["source"]) not in existing_rules
        ],
    )


def _insert_demo_case(conn: sqlite3.Connection, case: dict) -> None:
    record = {
        **{column: case.get(column) for column in case_store.WRITABLE_COLUMNS if column in case},
        "applicant": case.get("applicant") or "",
        "subject": case.get("subject") or "",
        "status": case.get("status") or CaseStatus.brak_dzialan,
        "procedure_mode": case.get("procedure_mode") or ProcedureMode.zwykla,
        "source": DEMO_SOURCE,
    }
    case_id = case_store.insert(conn, record)
    case_store.set_archived_departments(conn, case_id, record, case.get("departments") or [])
    for document in case.get("documents", []):
        case_store.add_document(
            conn, case_id, document["kind"], document["text"],
            filename=document.get("filename"), document_date=document.get("document_date"),
        )
        case_store.log_event(conn, case_id, document["kind"], document.get("filename"))
