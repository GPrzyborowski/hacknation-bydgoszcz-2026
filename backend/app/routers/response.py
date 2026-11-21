"""Etap 4: anonimizacja, eksport DOCX/PDF i oznaczenie wysyłki (wysyłkę wykonuje urzędnik poza systemem)."""
import re
import sqlite3
from datetime import date
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Response

import db
from db import db_dependency
from routers.common import get_case_row
from schemas import AnonymizationCandidate, AnonymizePreviewRequest, GenerateRequest, SendRequest, SendResponse
from services import anonymization, documents

router = APIRouter(prefix="/api/response", tags=["3. Odpowiedź i anonimizacja"])


def _draft(conn: sqlite3.Connection, draft_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM response_drafts WHERE id = ?", (draft_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"Nie znaleziono projektu odpowiedzi o id {draft_id}.")
    return row


@router.post(
    "/generate",
    response_class=Response,
    responses={200: {"content": {documents.DOCX_MIME: {}, documents.PDF_MIME: {}, "text/plain": {}}, "description": "Plik odpowiedzi"}},
)
def generate(body: GenerateRequest, conn: sqlite3.Connection = Depends(db_dependency)):
    """Nakłada zatwierdzone anonimizacje (pozycje `active: false` są pomijane), ustawia status
    `przygotowana_odpowiedz` i zwraca plik. Oryginalne dane z zamaskowanych fragmentów nie trafiają do pliku."""
    draft = _draft(conn, body.draft_id)
    case = dict(get_case_row(conn, draft["case_id"]))
    items = [i.model_dump() for i in body.anonymization_items]
    for item in items:
        if not (0 <= item["start"] < item["end"] <= len(body.content)):
            raise HTTPException(400, f"Zakres anonimizacji {item['start']}–{item['end']} wykracza poza treść pisma.")
    redacted = anonymization.apply(body.content, items)

    conn.execute(
        "UPDATE response_drafts SET final_text = ?, generated_format = ?, updated_at = datetime('now') WHERE id = ?",
        (redacted, body.format, body.draft_id),
    )
    # Kwerenda i wezwanie do doprecyzowania to pisma w toku sprawy — status zostaje (kwerenda / doprecyzowanie).
    if case["status"] != "odpowiedz_wyslana" and draft["kind"] in ("odpowiedz", "nie_dysponent"):
        conn.execute("UPDATE cases SET status = 'przygotowana_odpowiedz', updated_at = datetime('now') WHERE id = ?", (case["id"],))
    db.log_event(conn, case["id"], "wygenerowano_odpowiedz", f"format {body.format}, zanonimizowano {sum(i['active'] for i in items)} fragm.")

    if body.format == "pdf":
        content, mime = documents.build_pdf(case, redacted, items), documents.PDF_MIME
    elif body.format == "txt":
        content, mime = redacted.encode("utf-8"), "text/plain; charset=utf-8"
    else:
        content, mime = documents.build_docx(case, redacted, items), documents.DOCX_MIME

    safe = re.sub(r"[^\w.-]+", "_", case["case_number"]) or "odpowiedz"
    filename = f"odpowiedz_{safe}.{body.format}"
    return Response(
        content=content,
        media_type=mime,
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\"; filename*=UTF-8''{quote(filename)}",
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.post("/send", response_model=SendResponse)
def send(body: SendRequest, conn: sqlite3.Connection = Depends(db_dependency)):
    """Oznacza sprawę jako `odpowiedz_wyslana`, zapisuje datę i treść odpowiedzi oraz aktualizuje `cases_fts`,
    dzięki czemu sprawa zasila archiwum podobnych spraw. System NIE wysyła pisma — robi to urzędnik."""
    case = get_case_row(conn, body.case_id)
    kind = "odpowiedz"
    if body.draft_id is not None:
        draft = _draft(conn, body.draft_id)
        if draft["case_id"] != body.case_id:
            raise HTTPException(400, "Projekt odpowiedzi należy do innej sprawy.")
        kind = draft["kind"]
        conn.execute(
            "UPDATE response_drafts SET final_text = ?, updated_at = datetime('now') WHERE id = ?", (body.final_content, body.draft_id)
        )
    response_date = (body.response_date or date.today()).isoformat()
    conn.execute(
        "INSERT INTO case_documents(case_id, kind, filename, text, document_date) VALUES (?, ?, NULL, ?, ?)",
        (body.case_id, kind, body.final_content, response_date),
    )
    if kind in ("kwerenda", "doprecyzowanie"):
        # Pismo w toku sprawy: zapisujemy je w aktach, sprawa pozostaje otwarta z nowym terminem.
        db.log_event(conn, body.case_id, f"{kind}_wyslane", response_date)
        return {"case_id": body.case_id, "status": case["status"], "response_date": response_date}
    conn.execute(
        "UPDATE cases SET status = 'odpowiedz_wyslana', response_date = ?, response_text = ?, updated_at = datetime('now') WHERE id = ?",
        (response_date, body.final_content, body.case_id),
    )
    db.index_case(conn, body.case_id)
    db.log_event(conn, body.case_id, "odpowiedz_wyslana", response_date)
    return {"case_id": body.case_id, "status": "odpowiedz_wyslana", "response_date": response_date}


@router.post("/anonymize-preview", response_model=list[AnonymizationCandidate])
def anonymize_preview(body: AnonymizePreviewRequest, conn: sqlite3.Connection = Depends(db_dependency)):
    """Ponowne wyliczenie kandydatów (regexy + znane osoby) po ręcznej edycji treści przez urzędnika — bez LLM."""
    return anonymization.find_candidates(conn, body.text, None, body.known_people)
