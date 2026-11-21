"""Etapy 2–3: rejestr wniosków (kalendarz), statusy, odpowiedzi z wydziałów → projekt pisma."""
import json
import sqlite3
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile

import config
import db
from db import db_dependency
from routers.common import case_list_item, get_case_row, http_errors, read_upload, validate_departments
from schemas import (
    CaseDetail,
    CaseListItem,
    CaseStatus,
    ClarificationIn,
    ClarificationOut,
    DepartmentAdd,
    DepartmentReplyResponse,
    DepartmentStatusOut,
    DepartmentStatusUpdate,
    LetterKind,
    LetterRequest,
    RegisterCase,
    RegisterResponse,
    StatusResponse,
    StatusUpdate,
    UpdateCase,
)
from services import analysis, anonymization, deadlines, dept_tracking, extraction, letters, search

router = APIRouter(prefix="/api/cases", tags=["2. Rejestr wniosków"])


@router.get("", response_model=list[CaseListItem])
def list_cases(
    year: int | None = Query(None, description="Rok sprawy, np. 2026"),
    q: str | None = Query(None, description="Wyszukiwanie pełnotekstowe (cases_fts)"),
    status: CaseStatus | None = Query(None),
    conn: sqlite3.Connection = Depends(db_dependency),
):
    """Lista spraw od najstarszych (received_date ASC, id ASC) z `days_remaining` i `urgency` do podświetlania."""
    sql = "SELECT * FROM cases WHERE 1=1"
    params: list = []
    if year is not None:
        sql += " AND year = ?"
        params.append(year)
    if status is not None:
        sql += " AND status = ?"
        params.append(status.value)
    if q and q.strip():
        ids = search.search_case_ids(conn, q)
        if ids is not None:
            if not ids:
                return []
            sql += f" AND id IN ({','.join('?' * len(ids))})"
            params += ids
    sql += " ORDER BY received_date IS NULL, received_date ASC, id ASC"
    summary = dept_tracking.summary(conn)
    return [case_list_item(r, summary.get(r["id"])) for r in conn.execute(sql, params).fetchall()]


@router.get("/years", response_model=list[int])
def list_years(conn: sqlite3.Connection = Depends(db_dependency)):
    """Lata, dla których są sprawy — do przełącznika roku w kalendarzu."""
    return [r[0] for r in conn.execute("SELECT DISTINCT year FROM cases ORDER BY year DESC")]


@router.get("/{case_id}", response_model=CaseDetail)
def get_case(case_id: int, conn: sqlite3.Connection = Depends(db_dependency)):
    row = get_case_row(conn, case_id)
    item = case_list_item(row, dept_tracking.summary(conn).get(case_id))
    replies = conn.execute(
        "SELECT id, department, filename, text, created_at FROM department_replies WHERE case_id = ? ORDER BY id", (case_id,)
    ).fetchall()
    drafts = conn.execute("SELECT * FROM response_drafts WHERE case_id = ? ORDER BY id DESC", (case_id,)).fetchall()
    events = conn.execute(
        "SELECT event, detail, created_at FROM case_events WHERE case_id = ? ORDER BY id", (case_id,)
    ).fetchall()
    documents = conn.execute(
        "SELECT id, kind, filename, text, document_date, created_at FROM case_documents WHERE case_id = ? ORDER BY id", (case_id,)
    ).fetchall()
    return {
        **item,
        "applicant_contact": row["applicant_contact"],
        "department_status": dept_tracking.for_case(conn, case_id),
        "documents": [dict(d) for d in documents],
        "request_text": row["request_text"],
        "parsed_request": json.loads(row["parsed_request"]) if row["parsed_request"] else None,
        "response_text": row["response_text"],
        "department_replies": [dict(r) for r in replies],
        "drafts": [
            {
                "id": d["id"],
                "kind": d["kind"],
                "draft_text": d["draft_text"],
                "anonymization_candidates": json.loads(d["anonymization_candidates"] or "[]"),
                "final_text": d["final_text"],
                "generated_format": d["generated_format"],
                "llm_used": bool(d["llm_used"]),
                "created_at": d["created_at"],
            }
            for d in drafts
        ],
        "events": [dict(e) for e in events],
    }


def _next_case_number(conn: sqlite3.Connection, year: int) -> str:
    prefix = f"{config.CASE_NUMBER_PREFIX}."
    max_n = 0
    for (number,) in conn.execute("SELECT case_number FROM cases WHERE year = ? AND case_number LIKE ?", (year, prefix + "%")):
        middle = number[len(prefix):].rsplit(".", 1)[0]
        if middle.isdigit():
            max_n = max(max_n, int(middle))
    return f"{prefix}{max_n + 1}.{year}"


@router.post("/register", response_model=RegisterResponse, status_code=201)
def register_case(body: RegisterCase, conn: sqlite3.Connection = Depends(db_dependency)):
    """Rejestruje wniosek po weryfikacji/edycji danych przez urzędnika. Z wydziałami → `zapytania_wyslane`,
    bez → `brak_dzialan`. Szablony próśb do wydziałów to wyłącznie propozycje tekstu — nic nie jest wysyłane."""
    year = body.year or body.received_date.year
    departments = validate_departments(conn, body.departments)
    case_number = (body.case_number or "").strip() or _next_case_number(conn, year)
    if conn.execute("SELECT 1 FROM cases WHERE case_number = ?", (case_number,)).fetchone():
        raise HTTPException(409, f"Sprawa o znaku {case_number} już istnieje.")

    deadline = body.deadline_date or deadlines.default_deadline(body.received_date)
    status = CaseStatus.zapytania_wyslane if departments else CaseStatus.brak_dzialan

    request_text, parsed = None, body.parsed_request.model_dump() if body.parsed_request else None
    if body.intake_id is not None:
        intake = conn.execute("SELECT * FROM intakes WHERE id = ?", (body.intake_id,)).fetchone()
        if intake is None:
            raise HTTPException(404, f"Nie znaleziono analizy wniosku (intake_id={body.intake_id}).")
        request_text = intake["text"]
        if parsed is None and intake["parsed_json"]:
            parsed = json.loads(intake["parsed_json"])

    ordinal = conn.execute("SELECT COALESCE(MAX(ordinal), 0) + 1 FROM cases WHERE year = ?", (year,)).fetchone()[0]
    cur = conn.execute(
        """
        INSERT INTO cases(case_number, year, ordinal, applicant, applicant_contact, subject, received_date, deadline_date,
                          original_deadline_date, status, procedure_mode, departments, initials, notes, request_text,
                          parsed_request, intake_id, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ui')
        """,
        (
            case_number, year, ordinal, body.applicant, body.applicant_contact, body.subject,
            body.received_date.isoformat(), deadline.isoformat(),
            deadlines.default_deadline(body.received_date).isoformat(), status.value, body.procedure_mode,
            analysis.dumps(departments), body.initials, body.notes, request_text,
            analysis.dumps(parsed) if parsed else None, body.intake_id,
        ),
    )
    case_id = cur.lastrowid
    dept_tracking.sync(conn, case_id, departments)
    if request_text:
        conn.execute(
            "INSERT INTO case_documents(case_id, kind, filename, text, document_date) VALUES (?, 'wniosek', ?, ?, ?)",
            (case_id, intake["filename"], request_text, body.received_date.isoformat()),
        )
    db.index_case(conn, case_id)
    db.log_event(conn, case_id, "rejestracja", f"status: {status.value}")

    templates: dict[str, str] = {}
    if body.generate_dept_request_template and departments:
        dept_names = {d["code"]: d for d in search.departments(conn)}
        questions = (parsed or {}).get("pytania") or []
        # Wydziałowi dajemy 7 dni przed terminem ustawowym (min. dziś + 2 dni robocze).
        dept_deadline = deadlines.shift_to_working_day(
            max(date.fromordinal(deadline.toordinal() - 7), date.fromordinal(date.today().toordinal() + 2))
        )
        case_ctx = {"case_number": case_number, "received_date": body.received_date.isoformat(), "subject": body.subject}
        for code in departments:
            templates[code] = analysis.department_request_template(case_ctx, dept_names[code], questions, dept_deadline.isoformat())

    return {
        "id": case_id,
        "case_number": case_number,
        "status": status,
        "deadline_date": deadline.isoformat(),
        "departments": departments,
        "request_templates": templates,
    }


@router.patch("/{case_id}", response_model=CaseListItem)
def update_case(case_id: int, body: UpdateCase, conn: sqlite3.Connection = Depends(db_dependency)):
    """Korekta danych sprawy (termin, inicjały, numer, wydziały…) — urzędnik akceptuje/zmienia dane."""
    get_case_row(conn, case_id)
    changes = body.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(400, "Brak pól do zmiany.")
    new_departments = None
    if "departments" in changes:
        new_departments = validate_departments(conn, changes["departments"] or [])
        changes["departments"] = analysis.dumps(new_departments)
    for key in ("received_date", "deadline_date", "response_date"):
        if isinstance(changes.get(key), date):
            changes[key] = changes[key].isoformat()
    if "received_date" in changes and changes["received_date"]:
        changes["year"] = int(changes["received_date"][:4])
    sets = ", ".join(f"{k} = ?" for k in changes)
    conn.execute(f"UPDATE cases SET {sets}, updated_at = datetime('now') WHERE id = ?", (*changes.values(), case_id))
    if new_departments is not None:
        dept_tracking.sync(conn, case_id, new_departments)
    db.index_case(conn, case_id)
    db.log_event(conn, case_id, "edycja", ", ".join(changes))
    return case_list_item(get_case_row(conn, case_id))


@router.delete("/{case_id}", status_code=204)
def delete_case(case_id: int, conn: sqlite3.Connection = Depends(db_dependency)):
    get_case_row(conn, case_id)
    conn.execute("DELETE FROM cases WHERE id = ?", (case_id,))
    db.index_case(conn, case_id)  # usuwa wpis z cases_fts
    return Response(status_code=204)


@router.patch("/{case_id}/status", response_model=StatusResponse)
def update_status(case_id: int, body: StatusUpdate, conn: sqlite3.Connection = Depends(db_dependency)):
    """Ręczna zmiana statusu. Dla `kwerenda` bez podanego terminu ustawia termin maksymalny (2 miesiące, art. 13 ust. 2)."""
    row = get_case_row(conn, case_id)
    deadline = body.deadline_date
    received = deadlines.from_iso(row["received_date"])
    if body.status == CaseStatus.kwerenda and deadline is None and received:
        deadline = deadlines.extended_deadline(received)
    if deadline and received and deadline > deadlines.extended_deadline(received):
        raise HTTPException(400, "Termin nie może przekraczać 2 miesięcy od dnia złożenia wniosku (art. 13 ust. 2 u.d.i.p.).")

    response_date = row["response_date"]
    if body.status == CaseStatus.odpowiedz_wyslana and not response_date:
        response_date = date.today().isoformat()
    conn.execute(
        "UPDATE cases SET status = ?, deadline_date = COALESCE(?, deadline_date), response_date = ?, updated_at = datetime('now') WHERE id = ?",
        (body.status.value, deadline.isoformat() if deadline else None, response_date, case_id),
    )
    detail = body.status.value + (f", termin {deadline.isoformat()}" if deadline else "") + (f" — {body.note}" if body.note else "")
    db.log_event(conn, case_id, "status", detail)
    item = case_list_item(get_case_row(conn, case_id))
    return {"case_id": case_id, "status": body.status, "deadline_date": item["deadline_date"], "days_remaining": item["days_remaining"]}


@router.post(
    "/{case_id}/department-reply",
    response_model=DepartmentReplyResponse,
    responses={400: {"description": "Brak pliku i tekstu / zły format."}, 403: {}, 422: {}, 502: {}},
)
def department_reply(
    case_id: int,
    file: UploadFile | None = File(None, description=".docx / .pdf / .doc / skan z wydziału"),
    reply_text: str | None = Form(None, description="Treść odpowiedzi wpisana lub wklejona ręcznie"),
    department: str | None = Form(None, description="Symbol komórki, np. WIM (opcjonalnie)"),
    conn: sqlite3.Connection = Depends(db_dependency),
):
    """Zapisuje materiał z wydziału, ustawia status `odpowiedz_w_przygotowaniu`, generuje projekt odpowiedzi
    (ze wszystkich dotychczasowych materiałów) i kandydatów do anonimizacji. Projekt wymaga weryfikacji urzędnika."""
    row = get_case_row(conn, case_id)
    if (file is None or not file.filename) and not (reply_text and reply_text.strip()):
        raise HTTPException(400, "Dołącz plik z odpowiedzią wydziału albo wpisz jej treść.")
    if department:
        department = validate_departments(conn, [department])[0]

    texts, filename = [], None
    with http_errors():
        if file is not None and file.filename:
            filename = file.filename
            texts.append(extraction.extract(filename, read_upload(file)).text)
    if reply_text and reply_text.strip():
        texts.append(reply_text.strip())
    conn.execute(
        "INSERT INTO department_replies(case_id, department, filename, text) VALUES (?, ?, ?, ?)",
        (case_id, department, filename, "\n\n".join(texts)),
    )
    answered = dept_tracking.mark_answered(conn, case_id, department)
    if answered:
        db.log_event(conn, case_id, "wydzial_odpowiedzial", answered)
    row = get_case_row(conn, case_id)

    replies = [dict(r) for r in conn.execute("SELECT department, filename, text FROM department_replies WHERE case_id = ? ORDER BY id", (case_id,))]
    case = dict(row)
    parsed = json.loads(row["parsed_request"]) if row["parsed_request"] else None
    rules = search.relevant_rules(conn, f"{row['subject']} {' '.join(r['text'][:500] for r in replies)}")
    cats = [c["name"] for c in anonymization.categories(conn)]

    dept_codes = list(dict.fromkeys([r["department"] for r in replies if r["department"]] + json.loads(row["departments"] or "[]")))
    dept_names = _department_names(conn, dept_codes)
    # Wzór stylu: odpowiedź z najbardziej podobnej zakończonej sprawy z archiwum UMB.
    similar = search.similar_cases(conn, f"{row['subject']} {row['request_text'] or ''}"[:3000], limit=3, exclude_id=case_id)
    example = next((s["response_text"] for s in similar if s["response_text"]), None)

    with http_errors():
        draft_text, llm_candidates, llm_used = analysis.draft_reply(
            case, row["request_text"] or "", parsed, replies, rules, cats, dept_names, example
        )

    draft = _save_draft(conn, row, parsed, draft_text, llm_candidates, llm_used, "odpowiedz")
    conn.execute(
        "UPDATE cases SET status = 'odpowiedz_w_przygotowaniu', updated_at = datetime('now') WHERE id = ?", (case_id,)
    )
    db.log_event(conn, case_id, "odpowiedz_wydzialu", f"{department or 'wydział'}{' — ' + filename if filename else ''}")
    return {"case_id": case_id, "status": CaseStatus.odpowiedz_w_przygotowaniu, "kind": "odpowiedz", **draft}


def _department_names(conn: sqlite3.Connection, codes: list[str]) -> list[str]:
    names = {r["code"]: r["name"] for r in conn.execute("SELECT code, name FROM departments")}
    return [names[c] for c in codes if c in names]


def _save_draft(conn, row, parsed, text: str, llm_candidates: list[dict], llm_used: bool, kind: str) -> dict:
    known_people = [row["applicant"]] + ([parsed.get("wnioskodawca")] if parsed and parsed.get("wnioskodawca") else [])
    candidates = anonymization.find_candidates(conn, text, llm_candidates, known_people)
    cur = conn.execute(
        "INSERT INTO response_drafts(case_id, draft_text, anonymization_candidates, llm_used, kind) VALUES (?, ?, ?, ?, ?)",
        (row["id"], text, analysis.dumps(candidates), int(llm_used), kind),
    )
    return {"draft_id": cur.lastrowid, "draft_text": text, "llm_used": llm_used, "anonymization_candidates": candidates}


@router.post("/{case_id}/letter", response_model=DepartmentReplyResponse)
def create_letter(case_id: int, body: LetterRequest, conn: sqlite3.Connection = Depends(db_dependency)):
    """Projekt pisma wg wzorów BKS UMB z materiałów wyzwania: `kwerenda` (przedłużenie terminu, art. 13 ust. 2),
    `doprecyzowanie` (wezwanie, 7 dni), `nie_dysponent` (wskazanie podmiotu właściwego) lub `odpowiedz` (szablon).
    Dla kwerendy/doprecyzowania ustawia status i nowy termin (`apply_status`). Pisma nie są nigdzie wysyłane."""
    row = get_case_row(conn, case_id)
    case = dict(row)
    parsed = json.loads(row["parsed_request"]) if row["parsed_request"] else None
    form = letters.addressee_form(row["applicant"], (parsed or {}).get("typ_wnioskodawcy"))
    received = deadlines.from_iso(row["received_date"])
    max_deadline = deadlines.extended_deadline(received) if received else None

    new_deadline = body.new_deadline
    if body.kind in (LetterKind.kwerenda, LetterKind.doprecyzowanie) and new_deadline is None:
        if not max_deadline:
            raise HTTPException(400, "Sprawa nie ma daty wpływu — podaj new_deadline.")
        # Kwerenda: maksymalny termin ustawowy; doprecyzowanie: 7 dni na odpowiedź + 14 dni na rozpatrzenie.
        proposal = max_deadline if body.kind == LetterKind.kwerenda else date.fromordinal(date.today().toordinal() + 21)
        new_deadline = min(proposal, max_deadline)
    if new_deadline and max_deadline and new_deadline > max_deadline:
        raise HTTPException(400, "Termin nie może przekraczać 2 miesięcy od dnia złożenia wniosku (art. 13 ust. 2 u.d.i.p.).")
    original = deadlines.from_iso(row["original_deadline_date"]) or (deadlines.default_deadline(received) if received else None)
    warning = None
    if body.kind == LetterKind.kwerenda:
        if new_deadline and original and new_deadline <= original:
            raise HTTPException(400, f"Nowy termin musi być późniejszy niż termin 14-dniowy ({original.strftime('%d.%m.%Y')}).")
        if original and date.today() > original:
            warning = (
                f"Termin 14-dniowy minął {original.strftime('%d.%m.%Y')}. Zgodnie z art. 13 ust. 2 u.d.i.p. powiadomienie "
                "o przedłużeniu powinno zostać wysłane przed jego upływem — zawiadomienie będzie spóźnione."
            )

    codes = [validate_departments(conn, [body.department])[0]] if body.department else json.loads(row["departments"] or "[]")
    dept_names = _department_names(conn, codes)

    if body.kind == LetterKind.kwerenda:
        text, status = letters.kwerenda(case, form, new_deadline), CaseStatus.kwerenda
    elif body.kind == LetterKind.doprecyzowanie:
        text, status = letters.doprecyzowanie(case, form, new_deadline, dept_names, body.details), CaseStatus.doprecyzowanie
    elif body.kind == LetterKind.nie_dysponent:
        entity = None
        if body.external_entity_id is not None:
            entity = conn.execute("SELECT * FROM external_entities WHERE id = ?", (body.external_entity_id,)).fetchone()
            if entity is None:
                raise HTTPException(404, f"Nie znaleziono podmiotu o id {body.external_entity_id}.")
        text, status = letters.nie_dysponent(case, form, dict(entity) if entity else None), CaseStatus.odpowiedz_w_przygotowaniu
        conn.execute("UPDATE cases SET procedure_mode = 'nie_dysponent' WHERE id = ?", (case_id,))
    else:
        replies = [dict(r) for r in conn.execute("SELECT department, filename, text FROM department_replies WHERE case_id = ?", (case_id,))]
        text = letters.answer(case, form, (parsed or {}).get("pytania") or [], replies, dept_names)
        status = CaseStatus.odpowiedz_w_przygotowaniu

    draft = _save_draft(conn, row, parsed, text, [], False, body.kind.value)
    if body.apply_status:
        conn.execute(
            "UPDATE cases SET status = ?, deadline_date = COALESCE(?, deadline_date), updated_at = datetime('now') WHERE id = ?",
            (status.value, new_deadline.isoformat() if new_deadline else None, case_id),
        )
        db.log_event(conn, case_id, body.kind.value, f"projekt pisma; termin {new_deadline.isoformat()}" if new_deadline else "projekt pisma")
    current = get_case_row(conn, case_id)
    return {
        "case_id": case_id,
        "status": current["status"],
        "kind": body.kind.value,
        "deadline_date": current["deadline_date"],
        "warning": warning,
        **draft,
    }


# --- ewidencja odpowiedzi wydziałów -----------------------------------------------------------

@router.post("/{case_id}/departments", response_model=list[DepartmentStatusOut], status_code=201)
def add_department(case_id: int, body: DepartmentAdd, conn: sqlite3.Connection = Depends(db_dependency)):
    """Dodaje wydział do sprawy (status „czeka na odpowiedź”)."""
    row = get_case_row(conn, case_id)
    code = validate_departments(conn, [body.code])[0]
    codes = json.loads(row["departments"] or "[]")
    if code in codes:
        raise HTTPException(409, f"Wydział {code} jest już w sprawie.")
    codes.append(code)
    conn.execute("UPDATE cases SET departments = ?, updated_at = datetime('now') WHERE id = ?", (analysis.dumps(codes), case_id))
    dept_tracking.sync(conn, case_id, codes)
    if row["status"] == "brak_dzialan":
        conn.execute("UPDATE cases SET status = 'zapytania_wyslane' WHERE id = ?", (case_id,))
    db.index_case(conn, case_id)
    db.log_event(conn, case_id, "zapytanie_do_wydzialu", code)
    return dept_tracking.for_case(conn, case_id)


@router.patch("/{case_id}/departments/{code}", response_model=list[DepartmentStatusOut])
def set_department_status(case_id: int, code: str, body: DepartmentStatusUpdate, conn: sqlite3.Connection = Depends(db_dependency)):
    """Ręczna zmiana statusu wydziału: `oczekuje`, `odpowiedzial`, `uszczegolowienie`."""
    get_case_row(conn, case_id)
    code = code.upper()
    if not conn.execute("SELECT 1 FROM case_departments WHERE case_id = ? AND code = ?", (case_id, code)).fetchone():
        raise HTTPException(404, f"Wydziału {code} nie ma w tej sprawie.")
    dept_tracking.set_status(conn, case_id, code, body.status, body.note)
    db.log_event(conn, case_id, f"wydzial_{body.status}", code)
    return dept_tracking.for_case(conn, case_id)


@router.delete("/{case_id}/departments/{code}", response_model=list[DepartmentStatusOut])
def remove_department(case_id: int, code: str, conn: sqlite3.Connection = Depends(db_dependency)):
    row = get_case_row(conn, case_id)
    codes = [c for c in json.loads(row["departments"] or "[]") if c != code.upper()]
    conn.execute("UPDATE cases SET departments = ? WHERE id = ?", (analysis.dumps(codes), case_id))
    dept_tracking.sync(conn, case_id, codes)
    db.index_case(conn, case_id)
    return dept_tracking.for_case(conn, case_id)


@router.post("/{case_id}/departments/{code}/clarification", response_model=ClarificationOut)
def request_clarification(case_id: int, code: str, body: ClarificationIn, conn: sqlite3.Connection = Depends(db_dependency)):
    """Prośba do wydziału o uszczegółowienie odpowiedzi: status wydziału → `uszczegolowienie`, zwraca treść
    pisma wewnętrznego do skopiowania (system niczego nie wysyła)."""
    row = get_case_row(conn, case_id)
    code = code.upper()
    if not conn.execute("SELECT 1 FROM case_departments WHERE case_id = ? AND code = ?", (case_id, code)).fetchone():
        raise HTTPException(404, f"Wydziału {code} nie ma w tej sprawie.")
    name = _department_names(conn, [code])
    last = conn.execute(
        "SELECT text FROM department_replies WHERE case_id = ? AND department = ? ORDER BY id DESC LIMIT 1", (case_id, code)
    ).fetchone()
    text = dept_tracking.clarification_request(dict(row), name[0] if name else code, body.details, last["text"] if last else None)
    dept_tracking.set_status(conn, case_id, code, dept_tracking.CLARIFICATION, body.details)
    db.log_event(conn, case_id, "prosba_o_uszczegolowienie", f"{code}: {body.details or ''}".strip(": "))
    return {"code": code, "text": text, "departments": dept_tracking.for_case(conn, case_id)}
