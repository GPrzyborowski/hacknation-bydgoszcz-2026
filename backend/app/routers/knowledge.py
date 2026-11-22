"""Baza wiedzy edytowalna z interfejsu: przepisy i zarządzenia, kategorie anonimizacji, komórki UMB,
podmioty zewnętrzne oraz archiwum spraw."""
import re
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

import db
from db import db_dependency
from errors import BadRequest, Conflict, NotFound
from routers.common import UPLOAD_ERRORS, read_upload
from schemas import (
    CategoryIn,
    CategoryOut,
    CategoryUpdate,
    DepartmentIn,
    DepartmentOut,
    DepartmentUpdate,
    ExternalEntityIn,
    ExternalEntityOut,
    ExternalEntityUpdate,
    ImportResult,
    ManualCase,
    ManualCaseOut,
    RuleIn,
    RuleOut,
    RuleUpdate,
)
from services import case_workflow, departments, excel_import, extraction, legal_text

router = APIRouter(prefix="/api/knowledge", tags=["4. Baza wiedzy"])


def _get(conn: sqlite3.Connection, table: str, key, *, key_column: str = "id", label: str) -> dict:
    """Wiersz albo 404 z komunikatem „Nie znaleziono {label} {key}.”, np. „reguły o id 5”."""
    row = conn.execute(f"SELECT * FROM {table} WHERE {key_column} = ?", (key,)).fetchone()
    if row is None:
        raise NotFound(f"Nie znaleziono {label} {key}.")
    return dict(row)


# --- przepisy i zarządzenia ------------------------------------------------------------------------

@router.get("/rules", response_model=list[RuleOut])
def list_rules(
    active_only: bool = False,
    q: str | None = Query(None, description="Szukaj w tytule, źródle i treści"),
    conn: sqlite3.Connection = Depends(db_dependency),
):
    conditions, params = [], []
    if active_only:
        conditions.append("is_active")
    if q:
        conditions.append("(title LIKE ? OR content LIKE ? OR source LIKE ?)")
        params += [f"%{q}%"] * 3
    where = " AND ".join(conditions) or "1"
    return [dict(row) for row in conn.execute(f"SELECT * FROM rules WHERE {where} ORDER BY id", params)]


@router.post("/rules", response_model=RuleOut, status_code=201)
def create_rule(body: RuleIn, conn: sqlite3.Connection = Depends(db_dependency)):
    cursor = conn.execute(
        "INSERT INTO rules(title, source, content, is_active) VALUES (?, ?, ?, ?)",
        (body.title, body.source, body.content, body.is_active),
    )
    return _get(conn, "rules", cursor.lastrowid, label="reguły o id")


@router.put("/rules/{rule_id}", response_model=RuleOut)
def update_rule(rule_id: int, body: RuleUpdate, conn: sqlite3.Connection = Depends(db_dependency)):
    _get(conn, "rules", rule_id, label="reguły o id")
    db.update_row(conn, "rules", "id", rule_id, body.model_dump(exclude_unset=True), touch=True)
    return _get(conn, "rules", rule_id, label="reguły o id")


@router.post("/rules/import-document", response_model=list[RuleOut], status_code=201, responses=UPLOAD_ERRORS)
def import_rule_document(
    file: UploadFile = File(description=".pdf / .docx / .txt z ustawą, zarządzeniem lub wzorem pisma"),
    title: str | None = Form(None),
    source: str | None = Form(None, description="np. „Zarządzenie nr 123/2026 Prezydenta Miasta”"),
    split_articles: bool = Form(True, description="Podziel dokument na artykuły i paragrafy (lepsze wyszukiwanie)"),
    conn: sqlite3.Connection = Depends(db_dependency),
):
    """Dzieli akt prawny na artykuły (Art. / §), żeby do projektu pisma trafiały tylko pasujące fragmenty."""
    filename = file.filename or "dokument.txt"
    text = extraction.extract(filename, read_upload(file), extraction.KNOWLEDGE_EXTENSIONS).text
    base_title = title or Path(filename).stem
    chunks = legal_text.split_units(text, base_title) if split_articles else [(base_title, legal_text.normalize(text))]
    ids = [
        conn.execute("INSERT INTO rules(title, source, content) VALUES (?, ?, ?)", (chunk_title, source or file.filename or "", content)).lastrowid
        for chunk_title, content in chunks
    ]
    placeholders = ",".join("?" * len(ids))
    return [dict(row) for row in conn.execute(f"SELECT * FROM rules WHERE id IN ({placeholders}) ORDER BY id", ids)]


# --- kategorie anonimizacji -----------------------------------------------------------------------

def _check_regex(pattern: str | None) -> None:
    if pattern:
        try:
            re.compile(pattern)
        except re.error as exc:
            raise BadRequest(f"Niepoprawne wyrażenie regularne: {exc}") from exc


@router.get("/anonymization-categories", response_model=list[CategoryOut])
def list_categories(conn: sqlite3.Connection = Depends(db_dependency)):
    return [dict(row) for row in conn.execute("SELECT * FROM anonymization_categories ORDER BY id")]


@router.post("/anonymization-categories", response_model=CategoryOut, status_code=201)
def create_category(body: CategoryIn, conn: sqlite3.Connection = Depends(db_dependency)):
    _check_regex(body.regex)
    cursor = conn.execute(
        "INSERT INTO anonymization_categories(name, legal_basis, regex, mask, is_active) VALUES (?, ?, ?, ?, ?)",
        (body.name, body.legal_basis, body.regex or None, body.mask, body.is_active),
    )
    return _get(conn, "anonymization_categories", cursor.lastrowid, label="kategorii o id")


@router.put("/anonymization-categories/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, body: CategoryUpdate, conn: sqlite3.Connection = Depends(db_dependency)):
    _get(conn, "anonymization_categories", category_id, label="kategorii o id")
    changes = body.model_dump(exclude_unset=True)
    _check_regex(changes.get("regex"))
    db.update_row(conn, "anonymization_categories", "id", category_id, changes)
    return _get(conn, "anonymization_categories", category_id, label="kategorii o id")


# --- komórki UMB -----------------------------------------------------------------------------------

@router.get("/departments", response_model=list[DepartmentOut])
def list_departments(conn: sqlite3.Connection = Depends(db_dependency)):
    return departments.list_all(conn)


@router.post("/departments", response_model=DepartmentOut, status_code=201)
def create_department(body: DepartmentIn, conn: sqlite3.Connection = Depends(db_dependency)):
    code = body.code.strip().upper()
    if code in departments.names(conn):
        raise Conflict(f"Komórka {code} już istnieje.")
    conn.execute(
        "INSERT INTO departments(code, name, keywords, is_active) VALUES (?, ?, ?, ?)",
        (code, body.name, body.keywords, body.is_active),
    )
    return _get(conn, "departments", code, key_column="code", label="komórki")


@router.put("/departments/{code}", response_model=DepartmentOut)
def update_department(code: str, body: DepartmentUpdate, conn: sqlite3.Connection = Depends(db_dependency)):
    code = code.upper()
    _get(conn, "departments", code, key_column="code", label="komórki")
    db.update_row(conn, "departments", "code", code, body.model_dump(exclude_unset=True))
    return _get(conn, "departments", code, key_column="code", label="komórki")


# --- podmioty spoza urzędu ----------------------------------------------------------------------------

@router.get("/external-entities", response_model=list[ExternalEntityOut])
def list_entities(conn: sqlite3.Connection = Depends(db_dependency)):
    """Podmioty, do których UMB odsyła wnioskodawcę (np. ZDMiKP, WKZ, Schronisko) — dane z pism UMB."""
    return [dict(row) for row in conn.execute("SELECT * FROM external_entities ORDER BY id")]


@router.post("/external-entities", response_model=ExternalEntityOut, status_code=201)
def create_entity(body: ExternalEntityIn, conn: sqlite3.Connection = Depends(db_dependency)):
    cursor = conn.execute(
        "INSERT INTO external_entities(name, name_genitive, contact, keywords, is_active) VALUES (?, ?, ?, ?, ?)",
        (body.name, body.name_genitive, body.contact, body.keywords, body.is_active),
    )
    return _get(conn, "external_entities", cursor.lastrowid, label="podmiotu o id")


@router.put("/external-entities/{entity_id}", response_model=ExternalEntityOut)
def update_entity(entity_id: int, body: ExternalEntityUpdate, conn: sqlite3.Connection = Depends(db_dependency)):
    _get(conn, "external_entities", entity_id, label="podmiotu o id")
    db.update_row(conn, "external_entities", "id", entity_id, body.model_dump(exclude_unset=True))
    return _get(conn, "external_entities", entity_id, label="podmiotu o id")


# --- archiwum spraw -------------------------------------------------------------------------------------

@router.post("/cases/manual", response_model=ManualCaseOut, status_code=201)
def add_manual_case(body: ManualCase, conn: sqlite3.Connection = Depends(db_dependency)):
    """Dopisuje wzorcową sprawę archiwalną (z udzieloną odpowiedzią) — zasila wyszukiwanie podobnych spraw."""
    return case_workflow.add_archived_case(conn, body)


@router.post("/cases/import-excel", response_model=ImportResult, responses=UPLOAD_ERRORS)
def import_excel(
    file: UploadFile = File(description="Rejestr wniosków .xlsx"),
    update_existing: bool = Form(True, description="Aktualizuj sprawy o tym samym znaku zamiast je pomijać"),
    conn: sqlite3.Connection = Depends(db_dependency),
):
    """Import spraw z arkusza. Kolumny rozpoznawane po nagłówkach (Lp., znak, data wpływu, termin, wnioskodawca,
    temat, wydział, osoba odpowiedzialna, data odpowiedzi, tryb, status, odpowiedź)."""
    if extraction.extension(file.filename or "") not in extraction.SPREADSHEET_EXTENSIONS:
        raise BadRequest("Oczekiwano pliku .xlsx.")
    records, warnings = excel_import.parse_workbook(read_upload(file), set(departments.names(conn)))
    return {**case_workflow.import_records(conn, records, update_existing), "warnings": warnings}
