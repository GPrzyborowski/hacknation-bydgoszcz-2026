"""Rejestr wniosków, tok sprawy, odpowiedzi wydziałów i projekty pism."""
import sqlite3

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile

from db import db_dependency
from domain import CaseStatus
from errors import BadRequest
from routers.common import LLM_ERRORS, UPLOAD_ERRORS, read_upload
from schemas import (
    CaseDetail,
    CaseListItem,
    ClarificationIn,
    ClarificationOut,
    DepartmentAdd,
    DepartmentStatusOut,
    DepartmentStatusUpdate,
    DraftResult,
    LetterRequest,
    RegisterCase,
    RegisterResponse,
    StatusResponse,
    StatusUpdate,
    UpdateCase,
)
from services import case_store, case_views, case_workflow, departments, drafting, extraction

router = APIRouter(prefix="/api/cases", tags=["2. Rejestr wniosków"])


@router.get("", summary="Rejestr wniosków", response_model=list[CaseListItem])
def list_cases(
    year: int | None = Query(None, description="Rok sprawy, np. 2026"),
    q: str | None = Query(None, description="Wyszukiwanie pełnotekstowe — wszystkie słowa muszą wystąpić"),
    status: CaseStatus | None = Query(None),
    open_only: bool = Query(False, description="Tylko sprawy w toku (bez wysłanej odpowiedzi)"),
    conn: sqlite3.Connection = Depends(db_dependency),
):
    """Sprawy od najstarszych z `days_remaining` i `urgency` do podświetlania pilnych."""
    return case_views.list_items(conn, year=year, status=status, open_only=open_only, query=q)


@router.get("/years", summary="Lata w rejestrze", response_model=list[int])
def list_years(conn: sqlite3.Connection = Depends(db_dependency)):
    """Lata, w których są sprawy — do przełącznika roku w rejestrze."""
    return [row[0] for row in conn.execute("SELECT DISTINCT year FROM cases ORDER BY year DESC")]


@router.get("/{case_id}", summary="Karta sprawy", response_model=CaseDetail)
def get_case(case_id: int, conn: sqlite3.Connection = Depends(db_dependency)):
    """Dane sprawy, statusy odpowiedzi wydziałów, dokumenty, materiały z wydziałów, projekty pism i historia zdarzeń."""
    return case_views.detail(conn, case_id)


@router.post("/register", summary="Rejestracja wniosku", response_model=RegisterResponse, status_code=201)
def register_case(body: RegisterCase, conn: sqlite3.Connection = Depends(db_dependency)):
    """Rejestruje wniosek po weryfikacji danych przez urzędnika. Z wydziałami → `zapytania_wyslane`,
    bez → `brak_dzialan`. Treść próśb do wydziałów to propozycja — nic nie jest wysyłane."""
    return case_workflow.register(conn, body)


@router.patch("/{case_id}", summary="Korekta danych sprawy", response_model=CaseListItem)
def update_case(case_id: int, body: UpdateCase, conn: sqlite3.Connection = Depends(db_dependency)):
    """Korekta danych sprawy (termin, osoba odpowiedzialna, znak, wydziały…)."""
    return case_workflow.update_details(conn, case_id, body)


@router.delete("/{case_id}", summary="Usunięcie sprawy", status_code=204)
def delete_case(case_id: int, conn: sqlite3.Connection = Depends(db_dependency)):
    """Usuwa sprawę wraz z dokumentami, projektami i historią."""
    case_store.delete(conn, case_id)
    return Response(status_code=204)


@router.patch("/{case_id}/status", summary="Zmiana statusu sprawy", response_model=StatusResponse)
def update_status(case_id: int, body: StatusUpdate, conn: sqlite3.Connection = Depends(db_dependency)):
    """Ręczna zmiana statusu. Kwerenda bez terminu dostaje termin maksymalny (2 miesiące, art. 13 ust. 2)."""
    return case_workflow.change_status(conn, case_id, body)


@router.post("/{case_id}/department-reply", summary="Materiał z wydziału → projekt odpowiedzi", response_model=DraftResult, responses={**UPLOAD_ERRORS, **LLM_ERRORS})
def department_reply(
    case_id: int,
    file: UploadFile | None = File(None, description=".docx / .pdf / .doc / skan z wydziału"),
    reply_text: str | None = Form(None, description="Treść odpowiedzi wpisana lub wklejona ręcznie"),
    department: str | None = Form(None, description="Symbol komórki, np. WIM (opcjonalnie)"),
    conn: sqlite3.Connection = Depends(db_dependency),
):
    """Zapisuje materiał z wydziału, ustawia status `odpowiedz_w_przygotowaniu` i przygotowuje projekt odpowiedzi
    ze wszystkich dotychczasowych materiałów wraz z kandydatami do anonimizacji. Projekt sprawdza urzędnik."""
    case_store.get(conn, case_id)
    has_file = file is not None and bool(file.filename)
    typed_text = (reply_text or "").strip()
    if not has_file and not typed_text:
        raise BadRequest("Dołącz plik z odpowiedzią wydziału albo wpisz jej treść.")
    department = departments.validate_one(conn, department) if department else None

    texts = [extraction.extract(file.filename, read_upload(file)).text] if has_file else []
    if typed_text:
        texts.append(typed_text)
    return drafting.draft_from_reply(conn, case_id, department, file.filename if has_file else None, "\n\n".join(texts))


@router.post("/{case_id}/letter", summary="Projekt pisma (kwerenda, doprecyzowanie, brak dysponenta)", response_model=DraftResult)
def create_letter(case_id: int, body: LetterRequest, conn: sqlite3.Connection = Depends(db_dependency)):
    """Projekt pisma według wzorów BKS UMB: `kwerenda` (przedłużenie terminu, art. 13 ust. 2), `doprecyzowanie`
    (wezwanie, 7 dni), `nie_dysponent` (wskazanie podmiotu właściwego) albo `odpowiedz` (szablon odpowiedzi)."""
    return drafting.draft_letter(
        conn, case_id, body.kind,
        new_deadline=body.new_deadline, external_entity_id=body.external_entity_id,
        department=body.department, details=body.details, apply_status=body.apply_status,
    )


@router.post("/{case_id}/departments", summary="Zapytanie kolejnego wydziału", response_model=list[DepartmentStatusOut], status_code=201)
def add_department(case_id: int, body: DepartmentAdd, conn: sqlite3.Connection = Depends(db_dependency)):
    """Dopisuje wydział do sprawy ze statusem „czeka na odpowiedź”."""
    return case_workflow.add_department(conn, case_id, body.code)


@router.patch("/{case_id}/departments/{code}", summary="Status odpowiedzi wydziału", response_model=list[DepartmentStatusOut])
def set_department_status(case_id: int, code: str, body: DepartmentStatusUpdate, conn: sqlite3.Connection = Depends(db_dependency)):
    """Statusy: `oczekuje`, `odpowiedzial`, `uszczegolowienie`."""
    return case_workflow.set_department_status(conn, case_id, code, body.status, body.note)


@router.delete("/{case_id}/departments/{code}", summary="Usunięcie wydziału ze sprawy", response_model=list[DepartmentStatusOut])
def remove_department(case_id: int, code: str, conn: sqlite3.Connection = Depends(db_dependency)):
    """Usuwa wydział ze sprawy (np. dopisany omyłkowo)."""
    return case_workflow.remove_department(conn, case_id, code)


@router.post("/{case_id}/departments/{code}/clarification", summary="Prośba do wydziału o uszczegółowienie", response_model=ClarificationOut)
def request_clarification(case_id: int, code: str, body: ClarificationIn, conn: sqlite3.Connection = Depends(db_dependency)):
    """Prośba do wydziału o uszczegółowienie odpowiedzi. Zwraca treść do skopiowania — system jej nie wysyła."""
    letter = drafting.clarification_request(conn, case_id, code.upper(), body.details)
    return {**letter, "departments": case_workflow.department_statuses(conn, case_id)}
