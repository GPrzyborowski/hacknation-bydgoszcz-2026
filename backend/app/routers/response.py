"""Anonimizacja, eksport pisma do DOCX/PDF i odnotowanie wysyłki (wysyła urzędnik, poza systemem)."""
import re
import sqlite3
from urllib.parse import quote

from fastapi import APIRouter, Depends, Response

from db import db_dependency
from domain import INTERIM_LETTERS, CaseStatus, LetterKind
from errors import BadRequest
from schemas import AnonymizationCandidate, AnonymizePreviewRequest, GenerateRequest, SendRequest, SendResponse
from services import anonymization, case_store, deadlines, documents, drafting

router = APIRouter(prefix="/api/response", tags=["3. Odpowiedź i anonimizacja"])

TEXT_MIME = "text/plain; charset=utf-8"


@router.post(
    "/generate",
    response_class=Response,
    responses={200: {"content": {documents.DOCX_MIME: {}, documents.PDF_MIME: {}, TEXT_MIME: {}}, "description": "Plik pisma"}},
)
def generate(body: GenerateRequest, conn: sqlite3.Connection = Depends(db_dependency)):
    """Nakłada zaznaczone anonimizacje (pozycje `active: false` są pomijane) i zwraca plik pisma. Projekt
    odpowiedzi przechodzi w status `przygotowana_odpowiedz`; oryginalne dane z masek nie trafiają do pliku."""
    draft = drafting.get_draft(conn, body.draft_id)
    case = case_store.get(conn, draft["case_id"])
    items = [item.model_dump() for item in body.anonymization_items]
    redaction = anonymization.apply(body.content, items)

    if body.format == "pdf":
        content, media_type = documents.build_pdf(case["case_number"], redaction.segments), documents.PDF_MIME
    elif body.format == "txt":
        content, media_type = redaction.text.encode("utf-8"), TEXT_MIME
    else:
        content, media_type = documents.build_docx(case["case_number"], redaction.segments), documents.DOCX_MIME

    conn.execute(
        "UPDATE response_drafts SET final_text = ?, generated_format = ?, updated_at = datetime('now') WHERE id = ?",
        (redaction.text, body.format, body.draft_id),
    )
    if case["status"] != CaseStatus.odpowiedz_wyslana and draft["kind"] not in INTERIM_LETTERS:
        case_store.set_status(conn, case["id"], CaseStatus.przygotowana_odpowiedz)
    masked = sum(item["active"] for item in items)
    case_store.log_event(conn, case["id"], "wygenerowano_odpowiedz", f"format {body.format}, zanonimizowano {masked} fragm.")

    safe_case_number = re.sub(r"[^\w.-]+", "_", case["case_number"]) or "odpowiedz"
    filename = f"odpowiedz_{safe_case_number}.{body.format}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\"; filename*=UTF-8''{quote(filename)}"},
    )


@router.post("/send", response_model=SendResponse)
def send(body: SendRequest, conn: sqlite3.Connection = Depends(db_dependency)):
    """Odnotowuje wysłanie pisma i zapisuje je w aktach — po zamaskowaniu zaznaczonych fragmentów. Odpowiedź
    zamyka sprawę i zasila archiwum podobnych spraw; kwerenda i doprecyzowanie pozostawiają sprawę w toku."""
    case = case_store.get(conn, body.case_id)
    text = anonymization.apply(body.final_content, [item.model_dump() for item in body.anonymization_items]).text
    kind = LetterKind.odpowiedz
    if body.draft_id is not None:
        draft = drafting.get_draft(conn, body.draft_id)
        if draft["case_id"] != body.case_id:
            raise BadRequest("Projekt odpowiedzi należy do innej sprawy.")
        kind = draft["kind"]
        conn.execute(
            "UPDATE response_drafts SET final_text = ?, updated_at = datetime('now') WHERE id = ?", (text, body.draft_id)
        )

    response_date = (body.response_date or deadlines.today()).isoformat()
    case_store.add_document(conn, body.case_id, kind, text, document_date=response_date)
    if kind in INTERIM_LETTERS:
        case_store.log_event(conn, body.case_id, f"{kind}_wyslane", response_date)
        return {"case_id": body.case_id, "status": case["status"], "response_date": response_date}

    case_store.set_status(
        conn, body.case_id, CaseStatus.odpowiedz_wyslana, response_date=response_date, response_text=text,
        event="odpowiedz_wyslana", detail=response_date,
    )
    return {"case_id": body.case_id, "status": CaseStatus.odpowiedz_wyslana, "response_date": response_date}


@router.post("/anonymize-preview", response_model=list[AnonymizationCandidate])
def anonymize_preview(body: AnonymizePreviewRequest, conn: sqlite3.Connection = Depends(db_dependency)):
    """Kandydaci do anonimizacji po ręcznej edycji pisma (wzorce i znane osoby, bez modelu językowego)."""
    return anonymization.find_candidates(body.text, anonymization.load_categories(conn), known_people=body.known_people)
