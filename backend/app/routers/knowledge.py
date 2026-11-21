"""Baza wiedzy edytowalna z UI: przepisy/zarządzenia, kategorie anonimizacji, wydziały, archiwum spraw."""
import json
import re
import sqlite3
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

import db
from db import db_dependency
from routers.common import http_errors, read_upload, validate_departments
from schemas import (
    CategoryIn,
    CategoryOut,
    CategoryUpdate,
    DepartmentIn,
    DepartmentUpdate,
    ExternalEntityIn,
    ExternalEntityOut,
    ExternalEntityUpdate,
    ImportResult,
    ManualCase,
    RuleIn,
    RuleOut,
    RuleUpdate,
)
from services import analysis, excel_import, extraction, legal_text

router = APIRouter(prefix="/api/knowledge", tags=["4. Baza wiedzy"])


def _update(conn: sqlite3.Connection, table: str, key: str, key_value, changes: dict, touch: bool = True) -> None:
    if not changes:
        raise HTTPException(400, "Brak pól do zmiany.")
    for k, v in list(changes.items()):
        if isinstance(v, bool):
            changes[k] = int(v)
    sets = ", ".join(f"{k} = ?" for k in changes) + (", updated_at = datetime('now')" if touch else "")
    conn.execute(f"UPDATE {table} SET {sets} WHERE {key} = ?", (*changes.values(), key_value))


# --- przepisy / zarządzenia ----------------------------------------------------------------

def _rule(conn: sqlite3.Connection, rule_id: int) -> dict:
    row = conn.execute("SELECT * FROM rules WHERE id = ?", (rule_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"Nie znaleziono reguły o id {rule_id}.")
    return {**dict(row), "is_active": bool(row["is_active"])}


@router.get("/rules", response_model=list[RuleOut])
def list_rules(
    active_only: bool = False,
    q: str | None = Query(None, description="Szukaj w tytule/treści"),
    conn: sqlite3.Connection = Depends(db_dependency),
):
    sql, params = "SELECT * FROM rules WHERE 1=1", []
    if active_only:
        sql += " AND is_active = 1"
    if q:
        sql += " AND (title LIKE ? OR content LIKE ? OR source LIKE ?)"
        params += [f"%{q}%"] * 3
    return [{**dict(r), "is_active": bool(r["is_active"])} for r in conn.execute(sql + " ORDER BY id", params)]


@router.post("/rules", response_model=RuleOut, status_code=201)
def create_rule(body: RuleIn, conn: sqlite3.Connection = Depends(db_dependency)):
    cur = conn.execute(
        "INSERT INTO rules(title, source, content, is_active) VALUES (?, ?, ?, ?)",
        (body.title, body.source, body.content, int(body.is_active)),
    )
    db.index_rule(conn, cur.lastrowid)
    return _rule(conn, cur.lastrowid)


@router.put("/rules/{rule_id}", response_model=RuleOut)
def update_rule(rule_id: int, body: RuleUpdate, conn: sqlite3.Connection = Depends(db_dependency)):
    _rule(conn, rule_id)
    _update(conn, "rules", "id", rule_id, body.model_dump(exclude_unset=True))
    db.index_rule(conn, rule_id)
    return _rule(conn, rule_id)


@router.post("/rules/import-document", response_model=list[RuleOut], status_code=201)
def import_rule_document(
    file: UploadFile = File(..., description=".pdf / .docx / .txt z ustawą, zarządzeniem lub wzorem pisma"),
    title: str | None = Form(None),
    source: str | None = Form(None, description="np. „Zarządzenie nr 123/2026 Prezydenta Miasta”"),
    split_articles: bool = Form(True, description="Podziel dokument na artykuły/paragrafy (lepsze wyszukiwanie)"),
    conn: sqlite3.Connection = Depends(db_dependency),
):
    """Importuje dokument do bazy przepisów. Długie akty prawne są dzielone na artykuły (Art. / §), żeby
    przy projektowaniu odpowiedzi do modelu trafiały tylko pasujące fragmenty."""
    data = read_upload(file)
    with http_errors():
        text = extraction.extract(file.filename or "dokument.txt", data, extraction.KNOWLEDGE_EXTENSIONS).text
    base_title = title or Path(file.filename or "dokument").stem
    src = source or file.filename or ""

    chunks = legal_text.split_units(text, base_title) if split_articles else [(base_title, legal_text.normalize(text))]

    ids = []
    for chunk_title, content in chunks:
        cur = conn.execute("INSERT INTO rules(title, source, content) VALUES (?, ?, ?)", (chunk_title, src, content))
        db.index_rule(conn, cur.lastrowid)
        ids.append(cur.lastrowid)
    return [_rule(conn, i) for i in ids]


# --- kategorie anonimizacji ----------------------------------------------------------------

def _category(conn: sqlite3.Connection, category_id: int) -> dict:
    row = conn.execute("SELECT * FROM anonymization_categories WHERE id = ?", (category_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"Nie znaleziono kategorii o id {category_id}.")
    return {**dict(row), "is_active": bool(row["is_active"])}


def _check_regex(pattern: str | None) -> None:
    if pattern:
        try:
            re.compile(pattern)
        except re.error as exc:
            raise HTTPException(400, f"Niepoprawne wyrażenie regularne: {exc}") from exc


@router.get("/anonymization-categories", response_model=list[CategoryOut])
def list_categories(conn: sqlite3.Connection = Depends(db_dependency)):
    return [{**dict(r), "is_active": bool(r["is_active"])} for r in conn.execute("SELECT * FROM anonymization_categories ORDER BY id")]


@router.post("/anonymization-categories", response_model=CategoryOut, status_code=201)
def create_category(body: CategoryIn, conn: sqlite3.Connection = Depends(db_dependency)):
    _check_regex(body.regex)
    cur = conn.execute(
        "INSERT INTO anonymization_categories(name, legal_basis, regex, mask, is_active) VALUES (?, ?, ?, ?, ?)",
        (body.name, body.legal_basis, body.regex or None, body.mask, int(body.is_active)),
    )
    return _category(conn, cur.lastrowid)


@router.put("/anonymization-categories/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, body: CategoryUpdate, conn: sqlite3.Connection = Depends(db_dependency)):
    _category(conn, category_id)
    changes = body.model_dump(exclude_unset=True)
    _check_regex(changes.get("regex"))
    _update(conn, "anonymization_categories", "id", category_id, changes, touch=False)
    return _category(conn, category_id)


# --- wydziały / biura ----------------------------------------------------------------------

@router.get("/departments", response_model=list[DepartmentIn])
def list_departments(conn: sqlite3.Connection = Depends(db_dependency)):
    return [{**dict(r), "is_active": bool(r["is_active"])} for r in conn.execute("SELECT * FROM departments ORDER BY code")]


@router.post("/departments", response_model=DepartmentIn, status_code=201)
def create_department(body: DepartmentIn, conn: sqlite3.Connection = Depends(db_dependency)):
    code = body.code.strip().upper()
    if conn.execute("SELECT 1 FROM departments WHERE code = ?", (code,)).fetchone():
        raise HTTPException(409, f"Komórka {code} już istnieje.")
    conn.execute(
        "INSERT INTO departments(code, name, keywords, is_active) VALUES (?, ?, ?, ?)",
        (code, body.name, body.keywords, int(body.is_active)),
    )
    return {**body.model_dump(), "code": code}


@router.put("/departments/{code}", response_model=DepartmentIn)
def update_department(code: str, body: DepartmentUpdate, conn: sqlite3.Connection = Depends(db_dependency)):
    code = code.upper()
    if not conn.execute("SELECT 1 FROM departments WHERE code = ?", (code,)).fetchone():
        raise HTTPException(404, f"Nie znaleziono komórki {code}.")
    _update(conn, "departments", "code", code, body.model_dump(exclude_unset=True), touch=False)
    row = conn.execute("SELECT * FROM departments WHERE code = ?", (code,)).fetchone()
    return {**dict(row), "is_active": bool(row["is_active"])}


# --- podmioty zewnętrzne (gdy UMB nie jest dysponentem) ---------------------------------------

def _entity(conn: sqlite3.Connection, entity_id: int) -> dict:
    row = conn.execute("SELECT * FROM external_entities WHERE id = ?", (entity_id,)).fetchone()
    if row is None:
        raise HTTPException(404, f"Nie znaleziono podmiotu o id {entity_id}.")
    return {**dict(row), "is_active": bool(row["is_active"])}


@router.get("/external-entities", response_model=list[ExternalEntityOut])
def list_entities(conn: sqlite3.Connection = Depends(db_dependency)):
    """Podmioty, do których UMB odsyła wnioskodawcę (np. ZDMiKP, WKZ, Schronisko) — dane z pism UMB."""
    return [{**dict(r), "is_active": bool(r["is_active"])} for r in conn.execute("SELECT * FROM external_entities ORDER BY id")]


@router.post("/external-entities", response_model=ExternalEntityOut, status_code=201)
def create_entity(body: ExternalEntityIn, conn: sqlite3.Connection = Depends(db_dependency)):
    cur = conn.execute(
        "INSERT INTO external_entities(name, name_genitive, contact, keywords, is_active) VALUES (?, ?, ?, ?, ?)",
        (body.name, body.name_genitive, body.contact, body.keywords, int(body.is_active)),
    )
    return _entity(conn, cur.lastrowid)


@router.put("/external-entities/{entity_id}", response_model=ExternalEntityOut)
def update_entity(entity_id: int, body: ExternalEntityUpdate, conn: sqlite3.Connection = Depends(db_dependency)):
    _entity(conn, entity_id)
    _update(conn, "external_entities", "id", entity_id, body.model_dump(exclude_unset=True), touch=False)
    return _entity(conn, entity_id)


# --- archiwum spraw ------------------------------------------------------------------------

@router.post("/cases/manual", status_code=201)
def add_manual_case(body: ManualCase, conn: sqlite3.Connection = Depends(db_dependency)):
    """Dopisuje wzorcową sprawę archiwalną (z udzieloną odpowiedzią) do bazy i indeksu FTS5."""
    year = body.year or (body.received_date.year if body.received_date else None)
    if year is None:
        m = re.search(r"(20\d{2})\s*$", body.case_number)
        year = int(m.group(1)) if m else None
    if year is None:
        raise HTTPException(400, "Podaj rok sprawy lub datę wpływu.")
    departments = validate_departments(conn, body.departments)
    cur = conn.execute(
        """
        INSERT INTO cases(case_number, year, applicant, subject, received_date, deadline_date, response_date, status,
                          procedure_mode, departments, request_text, response_text, source)
        VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, 'archiwum')
        """,
        (
            body.case_number, year, body.applicant, body.subject,
            body.received_date.isoformat() if body.received_date else None,
            body.response_date.isoformat() if body.response_date else None,
            "odpowiedz_wyslana" if body.response_date or body.response_text else "brak_dzialan",
            body.procedure_mode, analysis.dumps(departments), body.request_text, body.response_text,
        ),
    )
    db.index_case(conn, cur.lastrowid)
    return {"id": cur.lastrowid, "case_number": body.case_number}


@router.post("/cases/import-excel", response_model=ImportResult)
def import_excel(
    file: UploadFile = File(..., description="Rejestr wniosków .xlsx"),
    update_existing: bool = Form(True, description="Aktualizuj sprawy o tym samym znaku zamiast je pomijać"),
    conn: sqlite3.Connection = Depends(db_dependency),
):
    """Import spraw z arkusza .xlsx. Kolumny rozpoznawane po nagłówkach (Lp., Nr/znak, data wpływu, termin,
    wnioskodawca, temat, wydział, inicjały, data odpowiedzi, tryb, status, odpowiedź)."""
    if extraction.extension(file.filename or "") not in {".xlsx", ".xlsm"}:
        raise HTTPException(400, "Oczekiwano pliku .xlsx.")
    data = read_upload(file)
    known = {r[0] for r in conn.execute("SELECT code FROM departments")}
    try:
        records, warnings = excel_import.parse_workbook(data, known)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    imported = updated = skipped = 0
    fields = [
        "case_number", "year", "ordinal", "applicant", "subject", "received_date", "deadline_date", "response_date",
        "date_parse_warning", "status", "procedure_mode", "departments", "initials", "notes", "response_text",
    ]
    for rec in records:
        rec["departments"] = json.dumps(rec["departments"], ensure_ascii=False)
        existing = conn.execute("SELECT id FROM cases WHERE case_number = ?", (rec["case_number"],)).fetchone()
        if existing:
            if not update_existing:
                skipped += 1
                continue
            sets = ", ".join(f"{f} = ?" for f in fields)
            conn.execute(f"UPDATE cases SET {sets}, updated_at = datetime('now') WHERE id = ?", (*[rec[f] for f in fields], existing[0]))
            case_id = existing[0]
            updated += 1
        else:
            cur = conn.execute(
                f"INSERT INTO cases({', '.join(fields)}, source) VALUES ({', '.join('?' * len(fields))}, 'excel')",
                [rec[f] for f in fields],
            )
            case_id = cur.lastrowid
            imported += 1
        db.index_case(conn, case_id)
    return {"imported": imported, "updated": updated, "skipped": skipped, "warnings": warnings}
