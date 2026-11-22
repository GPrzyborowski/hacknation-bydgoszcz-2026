"""Przyjęcie wniosku: przetworzone zgłoszenie, podobne sprawy, sugestie wydziałów i termin."""
import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, File, Form, UploadFile

from db import db_dependency
from errors import BadRequest
from routers.common import LLM_ERRORS, UPLOAD_ERRORS, read_upload
from schemas import IntakeResponse
from services import deadlines, extraction, intake

router = APIRouter(prefix="/api/intake", tags=["1. Przyjęcie wniosku"])


@router.post("/analyze", response_model=IntakeResponse, responses={**UPLOAD_ERRORS, **LLM_ERRORS})
def analyze(
    file: UploadFile = File(description="Wniosek: .pdf, .docx, .doc lub skan .jpg/.png/.tiff"),
    received_at: date | None = Form(None, description="Data wpływu (RRRR-MM-DD) — od niej liczony jest termin."),
    manual_text: str | None = Form(None, description="Treść wpisana przez urzędnika, gdy skan jest nieczytelny dla OCR."),
    conn: sqlite3.Connection = Depends(db_dependency),
):
    """Odczytuje tekst (PDF: warstwa tekstowa albo OCR), przetwarza go modelem do `parsed_request`, szuka podobnych
    spraw w archiwum i podpowiada komórki UMB. Niczego nie rejestruje — robi to `POST /api/cases/register`."""
    received = received_at or deadlines.today()
    if received > deadlines.today():
        raise BadRequest("Data wpływu nie może być późniejsza niż dzisiejsza.")
    filename = file.filename or "wniosek"
    if manual_text and manual_text.strip():
        extracted = extraction.manual_text(manual_text)
    else:
        extracted = extraction.extract(filename, read_upload(file))
    return intake.analyze(conn, filename, extracted, received)
