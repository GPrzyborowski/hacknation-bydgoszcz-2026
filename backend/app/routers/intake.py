"""Etap 1: przyjęcie wniosku → przetworzone zgłoszenie, podobne sprawy, sugestie wydziałów."""
import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from db import db_dependency
from routers.common import http_errors, read_upload
from schemas import IntakeResponse
from services import analysis, deadlines, extraction, search

router = APIRouter(prefix="/api/intake", tags=["1. Przyjęcie wniosku"])

ERRORS = {
    400: {"description": "Pusty plik lub nieobsługiwany format."},
    403: {"description": "OFFLINE_MODE=true i endpoint LLM spoza sieci lokalnej."},
    413: {"description": "Plik za duży."},
    422: {"description": "Brak warstwy tekstowej i brak możliwości wykonania OCR."},
    502: {"description": "Błąd komunikacji z LLM lub niepoprawny JSON zwrócony przez model."},
}


@router.post("/analyze", response_model=IntakeResponse, responses=ERRORS)
def analyze(
    file: UploadFile = File(..., description="Wniosek: .pdf, .docx, .doc lub skan .jpg/.png/.tiff"),
    received_at: date | None = Form(None, description="Data wpływu (RRRR-MM-DD) — do wyliczenia terminu."),
    manual_text: str | None = Form(
        None, description="Treść wniosku wpisana przez urzędnika — gdy skan jest nieczytelny dla OCR (np. pismo odręczne)."
    ),
    conn: sqlite3.Connection = Depends(db_dependency),
):
    """Wyciąga tekst (PDF: warstwa tekstowa albo OCR), przetwarza go przez LLM do `parsed_request`,
    szuka podobnych spraw w archiwum (`cases_fts`) i podpowiada komórki UMB. Niczego nie rejestruje —
    sprawa trafia do rejestru dopiero po zatwierdzeniu przez urzędnika (`POST /api/cases/register`)."""
    data = read_upload(file)
    filename = file.filename or "wniosek"
    if received_at and received_at > date.today():
        raise HTTPException(400, "Data wpływu nie może być późniejsza niż dzisiejsza.")

    manual = (manual_text or "").strip()
    with http_errors():
        try:
            extracted = extraction.extract(filename, data)
            meta = extracted.meta
            text = extracted.text
        except extraction.OcrUnavailable:
            if not manual:
                raise
            meta = {"has_text_layer": False, "used_ocr": True, "text_length": 0, "quality": 0.0,
                    "warning": "OCR nie odczytał dokumentu — użyto treści wpisanej ręcznie."}
            text = ""
        if manual:
            text = manual
            meta = {**meta, "text_length": len(manual), "manual_text_used": True}
        parsed, llm_depts, llm_used = analysis.parse_request(text, search.departments(conn))

    # Przy nieczytelnym skanie nie szukamy po „śmieciach” z OCR — tylko po tym, co da się wyodrębnić.
    readable = meta.get("quality", 1) >= extraction.LOW_QUALITY_THRESHOLD or bool(manual)
    if readable:
        query_text = " ".join([parsed["temat_skrot"], *parsed["pytania"], parsed["kategoria"], text[:3000]])
        similar = search.similar_cases(conn, query_text, limit=5)
        suggested = search.suggest_departments(conn, query_text, similar, llm_depts)
        external = search.suggest_external_entities(conn, query_text)
    else:
        similar, suggested, external = [], [], []
        parsed["uwagi"] = (parsed.get("uwagi") or "") + " Dokument nieczytelny dla OCR — wpisz treść (manual_text), aby wyszukać podobne sprawy."

    received = received_at or date.today()
    deadline = deadlines.default_deadline(received)
    suggested_deadline = {
        "received_date": received.isoformat(),
        "deadline_date": deadline.isoformat(),
        "max_extended_deadline": deadlines.extended_deadline(received).isoformat(),
        "days_remaining": deadlines.days_remaining(deadline),
        "note": deadlines.deadline_note(deadline),
    }

    cur = conn.execute(
        "INSERT INTO intakes(filename, text, parsed_json, received_date) VALUES (?, ?, ?, ?)",
        (filename, text, analysis.dumps(parsed), received.isoformat()),
    )
    return {
        "intake_id": cur.lastrowid,
        "filename": filename,
        "extraction": meta,
        "llm_used": llm_used,
        "parsed_request": parsed,
        "similar_cases": similar,
        "suggested_departments": suggested,
        "suggested_external_entities": external,
        "suggested_deadline": suggested_deadline,
        "initial_status": "brak_dzialan",
        "text_preview": text[:1500],
    }
