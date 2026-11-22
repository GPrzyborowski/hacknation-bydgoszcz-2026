"""Projekty pism w sprawie: odpowiedź z materiałów wydziałów oraz pisma według wzorów BKS UMB."""
import sqlite3
from datetime import date

import db
from domain import INTERIM_LETTERS, LETTER_STATUS, CaseStatus, DeptStatus, LetterKind, ProcedureMode
from errors import BadRequest, NotFound
from services import analysis, anonymization, case_store, deadlines, departments, dept_tracking, letters, search

RULES_QUERY_REPLY_CHARS = 500
SIMILAR_QUERY_CHARS = 3000


def draft_from_reply(conn: sqlite3.Connection, case_id: int, department: str | None, filename: str | None, text: str) -> dict:
    """Zapisuje materiał z wydziału i przygotowuje projekt odpowiedzi ze wszystkich dotychczasowych materiałów."""
    row = case_store.get(conn, case_id)
    parsed = case_store.parsed_request(row)
    replies = [*case_store.replies(conn, case_id), {"department": department, "filename": filename, "text": text}]
    dept_codes = list(dict.fromkeys([reply["department"] for reply in replies if reply["department"]] + dept_tracking.codes(conn, case_id)))
    dept_names = _names(conn, dept_codes)
    rules = search.relevant_rules(conn, f"{row['subject']} {' '.join(reply['text'][:RULES_QUERY_REPLY_CHARS] for reply in replies)}")
    categories = anonymization.load_categories(conn)
    similar = search.similar_cases(conn, f"{row['subject']} {row['request_text'] or ''}"[:SIMILAR_QUERY_CHARS], limit=3, exclude_id=case_id)
    example = next((case["response_text"] for case in similar if case["response_text"]), None)

    # Model wywołujemy przed pierwszym zapisem, żeby transakcja nie blokowała bazy na czas jego pracy.
    draft_text, llm_candidates, llm_used = analysis.draft_reply(
        dict(row), row["request_text"] or "", parsed, replies, rules, [c["name"] for c in categories], dept_names, example
    )

    case_store.add_reply(conn, case_id, department, filename, text)
    if answered := dept_tracking.mark_answered(conn, case_id, department):
        case_store.log_event(conn, case_id, "wydzial_odpowiedzial", answered)
    draft = save_draft(conn, row, categories, draft_text, llm_candidates, llm_used, LetterKind.odpowiedz)
    case_store.set_status(
        conn, case_id, CaseStatus.odpowiedz_w_przygotowaniu,
        event="odpowiedz_wydzialu", detail=f"{department or 'wydział'}{' — ' + filename if filename else ''}",
    )
    return {"case_id": case_id, "status": CaseStatus.odpowiedz_w_przygotowaniu, "kind": LetterKind.odpowiedz, **draft}


def draft_letter(
    conn: sqlite3.Connection,
    case_id: int,
    kind: LetterKind,
    *,
    new_deadline: date | None = None,
    external_entity_id: int | None = None,
    department: str | None = None,
    details: str | None = None,
    apply_status: bool = True,
) -> dict:
    """Pismo według wzoru UMB. Kwerenda i doprecyzowanie dostają nowy termin (maks. 2 miesiące od wpływu)."""
    row = case_store.get(conn, case_id)
    case = dict(row)
    parsed = case_store.parsed_request(row)
    form = letters.addressee_form(row["applicant"], parsed.get("typ_wnioskodawcy"))
    received = deadlines.from_iso(row["received_date"])

    if kind in INTERIM_LETTERS and new_deadline is None:
        if received is None:
            raise BadRequest("Sprawa nie ma daty wpływu — podaj new_deadline.")
        new_deadline = deadlines.proposed_letter_deadline(kind, received)
    deadlines.ensure_within_extension_limit(received, new_deadline)
    warning = None
    if kind == LetterKind.kwerenda and received and new_deadline:
        warning = deadlines.check_extension(received, new_deadline)

    dept_codes = [departments.validate_one(conn, department)] if department else dept_tracking.codes(conn, case_id)
    dept_names = _names(conn, dept_codes)

    if kind == LetterKind.kwerenda:
        text = letters.kwerenda(case, form, new_deadline)
    elif kind == LetterKind.doprecyzowanie:
        text = letters.doprecyzowanie(case, form, new_deadline, dept_names, details)
    elif kind == LetterKind.nie_dysponent:
        text = letters.nie_dysponent(case, form, _external_entity(conn, external_entity_id))
        case_store.update(conn, case_id, {"procedure_mode": ProcedureMode.nie_dysponent})
    else:
        text = letters.answer(case, form, parsed.get("pytania") or [], case_store.replies(conn, case_id), dept_names)

    draft = save_draft(conn, row, anonymization.load_categories(conn), text, [], False, kind)
    if apply_status:
        case_store.set_status(
            conn, case_id, LETTER_STATUS[kind], deadline=new_deadline,
            event=kind, detail=f"projekt pisma; termin {new_deadline.isoformat()}" if new_deadline else "projekt pisma",
        )
    current = case_store.get(conn, case_id)
    return {
        "case_id": case_id, "status": current["status"], "kind": kind,
        "deadline_date": current["deadline_date"], "warning": warning, **draft,
    }


def save_draft(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    categories: list[dict],
    text: str,
    llm_candidates: list[dict],
    llm_used: bool,
    kind: LetterKind,
) -> dict:
    parsed_applicant = case_store.parsed_request(row).get("wnioskodawca")
    known_people = [row["applicant"], *([parsed_applicant] if parsed_applicant else [])]
    candidates = anonymization.find_candidates(text, categories, llm_candidates, known_people)
    cursor = conn.execute(
        "INSERT INTO response_drafts(case_id, kind, draft_text, anonymization_candidates, llm_used) VALUES (?, ?, ?, ?, ?)",
        (row["id"], kind, text, db.to_json(candidates), llm_used),
    )
    return {"draft_id": cursor.lastrowid, "draft_text": text, "llm_used": llm_used, "anonymization_candidates": candidates}


def get_draft(conn: sqlite3.Connection, draft_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM response_drafts WHERE id = ?", (draft_id,)).fetchone()
    if row is None:
        raise NotFound(f"Nie znaleziono projektu odpowiedzi o id {draft_id}.")
    return row


def department_requests(conn: sqlite3.Connection, case: dict, dept_codes: list[str], questions: list[str], deadline: date) -> dict[str, str]:
    """Propozycje treści próśb do wydziałów — urzędnik kopiuje je i wysyła samodzielnie."""
    dept_deadline = deadlines.department_reply_deadline(deadline).isoformat()
    by_code = {dept["code"]: dept for dept in departments.list_all(conn)}
    return {code: letters.department_request(case, by_code[code], questions, dept_deadline) for code in dept_codes}


def clarification_request(conn: sqlite3.Connection, case_id: int, code: str, details: str | None) -> dict:
    """Prośba do wydziału o uszczegółowienie odpowiedzi; wydział dostaje status „uszczegółowienie”."""
    row = case_store.get(conn, case_id)
    name = _names(conn, [code])
    text = letters.clarification_request(dict(row), name[0] if name else code, details, case_store.last_reply_text(conn, case_id, code))
    dept_tracking.set_status(conn, case_id, code, DeptStatus.uszczegolowienie, details)
    case_store.log_event(conn, case_id, "prosba_o_uszczegolowienie", f"{code}: {details or ''}".strip(": "))
    return {"code": code, "text": text}


def _names(conn: sqlite3.Connection, codes: list[str]) -> list[str]:
    known = departments.names(conn)
    return [known[code] for code in codes if code in known]


def _external_entity(conn: sqlite3.Connection, entity_id: int | None) -> dict | None:
    if entity_id is None:
        return None
    row = conn.execute("SELECT * FROM external_entities WHERE id = ?", (entity_id,)).fetchone()
    if row is None:
        raise NotFound(f"Nie znaleziono podmiotu o id {entity_id}.")
    return dict(row)
