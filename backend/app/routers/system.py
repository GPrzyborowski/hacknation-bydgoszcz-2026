"""Stan backendu, konfiguracja dla interfejsu i kalendarz terminów ustawowych."""
from datetime import date

from fastapi import APIRouter, Query

import config
from errors import BadRequest
from schemas import AppConfig, DeadlineSuggestion, Health
from services import deadlines, extraction, llm

router = APIRouter(tags=["0. System"])

MAX_CALENDAR_RANGE_DAYS = 400


@router.get("/", summary="Stan backendu i modelu", response_model=Health)
def health():
    """Czy backend działa, czy wolno wysyłać treść do modelu (OFFLINE_MODE) i z jakim modelem pracuje."""
    return {"status": "ok", "offline_mode": config.OFFLINE_MODE, "model": llm.model_name(), "llm_enabled": llm.enabled()}


@router.get("/api/config", summary="Ustawienia dla interfejsu", response_model=AppConfig)
def app_config():
    """Prefiks znaku sprawy, dozwolone formaty i limit plików, liczby dni z przepisów oraz model — frontend nie trzyma tych wartości u siebie."""
    return {
        "case_number_prefix": config.CASE_NUMBER_PREFIX,
        "max_upload_mb": config.MAX_UPLOAD_MB,
        "request_extensions": list(extraction.REQUEST_EXTENSIONS),
        "knowledge_extensions": list(extraction.KNOWLEDGE_EXTENSIONS),
        "spreadsheet_extensions": list(extraction.SPREADSHEET_EXTENSIONS),
        "answer_days": deadlines.ANSWER_DAYS,
        "soon_days": deadlines.SOON_DAYS,
        "clarification_reply_days": deadlines.CLARIFICATION_REPLY_DAYS,
        "clarification_deadline_days": deadlines.CLARIFICATION_REPLY_DAYS + deadlines.ANSWER_DAYS,
        "model": llm.model_name(),
        "llm_enabled": llm.enabled(),
        "offline_mode": config.OFFLINE_MODE,
    }


@router.get("/api/deadlines/preview", summary="Podgląd terminu odpowiedzi", response_model=DeadlineSuggestion)
def deadline_preview(received: date = Query(description="Data wpływu wniosku (RRRR-MM-DD).")):
    """Termin odpowiedzi liczony tak samo jak przy rejestracji — do podglądu w formularzu."""
    return deadlines.suggestion(received)


@router.get("/api/deadlines/non-working-days", summary="Dni wolne od pracy w zakresie dat", response_model=list[date])
def non_working_days(start: date = Query(alias="from"), end: date = Query(alias="to")):
    """Soboty, niedziele i święta ustawowe w podanym zakresie — do wyróżnienia w kalendarium."""
    if end < start or (end - start).days > MAX_CALENDAR_RANGE_DAYS:
        raise BadRequest(f"Zakres dat musi być rosnący i krótszy niż {MAX_CALENDAR_RANGE_DAYS} dni.")
    return deadlines.non_working_days(start, end)
