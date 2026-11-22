"""Analiza wniosku przed rejestracją: przetworzone zgłoszenie, podobne sprawy, komórki właściwe i termin."""
import sqlite3
from datetime import date

import db
from services import analysis, deadlines, departments, search
from services.extraction import Extraction

SEARCH_QUERY_CHARS = 3000
PREVIEW_CHARS = 1500
UNREADABLE_NOTE = " Dokument nieczytelny dla OCR — wpisz treść (manual_text), aby wyszukać podobne sprawy."


def analyze(conn: sqlite3.Connection, filename: str, extracted: Extraction, received: date) -> dict:
    """Niczego nie rejestruje — sprawa powstaje dopiero po zatwierdzeniu danych przez urzędnika."""
    active_departments = departments.list_active(conn)
    parsed, llm_departments, llm_used = analysis.parse_request(extracted.text, active_departments)

    # Przy nieczytelnym skanie nie szukamy po błędach OCR — wyniki byłyby przypadkowe.
    similar, suggested, external = [], [], []
    if extracted.readable:
        query = " ".join([parsed["temat_skrot"], *parsed["pytania"], parsed["kategoria"], extracted.text[:SEARCH_QUERY_CHARS]])
        similar = search.similar_cases(conn, query)
        suggested = search.suggest_departments(query, similar, active_departments, llm_departments)
        external = search.suggest_external_entities(conn, query)
    else:
        parsed["uwagi"] = (parsed.get("uwagi") or "") + UNREADABLE_NOTE

    cursor = conn.execute(
        "INSERT INTO intakes(filename, text, parsed_json, received_date) VALUES (?, ?, ?, ?)",
        (filename, extracted.text, db.to_json(parsed), received.isoformat()),
    )
    return {
        "intake_id": cursor.lastrowid,
        "filename": filename,
        "extraction": extracted.meta,
        "llm_used": llm_used,
        "parsed_request": parsed,
        "similar_cases": similar,
        "suggested_departments": suggested,
        "suggested_external_entities": external,
        "suggested_deadline": deadlines.suggestion(received),
        "text_preview": extracted.text[:PREVIEW_CHARS],
    }
