"""Wczytanie danych testowych UMB (seed/umb_demo.json) przy pierwszym starcie.

Plik powstaje skryptem backend/scripts/build_demo_seed.py z materiałów wyzwania
(„Hacknation 2026 - UMB”): 10 spraw z rejestru WNIOSKI O UDOSTĘPNIANIE INFORMACJI PUBLICZNEJ.xlsx,
treści wniosków, odpowiedzi, pism (kwerenda, doprecyzowanie) oraz Zarządzenie nr 535/2024.
Wszystkie te dane są danymi testowymi organizatora (odpowiedzi zanonimizowane przez UMB).
"""
import json
import sqlite3

import config


def load_if_empty(conn: sqlite3.Connection) -> int:
    import db

    if not config.SEED_FILE.exists():
        return 0
    data = json.loads(config.SEED_FILE.read_text(encoding="utf-8"))

    loaded = 0
    if not conn.execute("SELECT 1 FROM cases LIMIT 1").fetchone():
        for case in data.get("cases", []):
            cur = conn.execute(
                """
                INSERT INTO cases(case_number, year, ordinal, applicant, subject, received_date, deadline_date, response_date,
                                  date_parse_warning, status, procedure_mode, departments, initials, notes, request_text,
                                  response_text, source)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'dane_testowe_umb')
                """,
                (
                    case["case_number"], case["year"], case.get("ordinal"), case.get("applicant") or "", case.get("subject") or "",
                    case.get("received_date"), case.get("deadline_date"), case.get("response_date"),
                    case.get("date_parse_warning"), case.get("status") or "brak_dzialan", case.get("procedure_mode") or "zwykla",
                    json.dumps(case.get("departments") or [], ensure_ascii=False), case.get("initials"), case.get("notes"),
                    case.get("request_text"), case.get("response_text"),
                ),
            )
            case_id = cur.lastrowid
            for doc in case.get("documents", []):
                conn.execute(
                    "INSERT INTO case_documents(case_id, kind, filename, text, document_date) VALUES (?, ?, ?, ?, ?)",
                    (case_id, doc["kind"], doc.get("filename"), doc["text"], doc.get("document_date")),
                )
                db.log_event(conn, case_id, doc["kind"], doc.get("filename"))
            db.index_case(conn, case_id)
            loaded += 1

    for rule in data.get("rules", []):
        exists = conn.execute("SELECT 1 FROM rules WHERE title = ? AND source = ?", (rule["title"], rule["source"])).fetchone()
        if not exists:
            cur = conn.execute("INSERT INTO rules(title, source, content) VALUES (?, ?, ?)", (rule["title"], rule["source"], rule["content"]))
            db.index_rule(conn, cur.lastrowid)
    return loaded
