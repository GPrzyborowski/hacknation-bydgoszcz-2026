"""Śledzenie odpowiedzi wydziałów w sprawie: które odpowiedziały, na które czekamy, gdzie poproszono o uszczegółowienie.

Zarządzenie nr 535/2024 § 10–11: AIP przekazuje zakres wniosku wydziałom, wydziały przesyłają projekt odpowiedzi
w terminie określonym przez AIP, a przy opóźnieniu powiadamiają AIP. Ten moduł prowadzi tę ewidencję.
"""
import json
import sqlite3
from datetime import date

PENDING = "oczekuje"
ANSWERED = "odpowiedzial"
CLARIFICATION = "uszczegolowienie"
STATUSES = (PENDING, ANSWERED, CLARIFICATION)

STATUS_LABELS = {
    PENDING: "czeka na odpowiedź",
    ANSWERED: "odpowiedział",
    CLARIFICATION: "poproszono o uszczegółowienie",
}


def sync(conn: sqlite3.Connection, case_id: int, codes: list[str], closed: bool = False) -> None:
    """Wydziały z pola sprawy ↔ wiersze ewidencji: dodaje brakujące, usuwa te, których już nie ma w sprawie."""
    existing = {r[0] for r in conn.execute("SELECT code FROM case_departments WHERE case_id = ?", (case_id,))}
    for code in codes:
        if code not in existing:
            conn.execute(
                "INSERT INTO case_departments(case_id, code, status, answered_at) VALUES (?, ?, ?, ?)",
                (case_id, code, ANSWERED if closed else PENDING, date.today().isoformat() if closed else None),
            )
    for code in existing - set(codes):
        conn.execute("DELETE FROM case_departments WHERE case_id = ? AND code = ?", (case_id, code))


def backfill(conn: sqlite3.Connection) -> None:
    """Sprawy sprzed wprowadzenia ewidencji: wydziały zakończonych spraw = odpowiedziały, pozostałych = oczekują."""
    rows = conn.execute(
        "SELECT id, departments, status, response_date, received_date FROM cases "
        "WHERE id NOT IN (SELECT DISTINCT case_id FROM case_departments)"
    ).fetchall()
    for row in rows:
        codes = json.loads(row["departments"] or "[]")
        closed = row["status"] in ("odpowiedz_wyslana", "przygotowana_odpowiedz")
        for code in codes:
            conn.execute(
                "INSERT OR IGNORE INTO case_departments(case_id, code, status, requested_at, answered_at) VALUES (?, ?, ?, ?, ?)",
                (row["id"], code, ANSWERED if closed else PENDING, row["received_date"] or date.today().isoformat(),
                 row["response_date"] if closed else None),
            )


def mark_answered(conn: sqlite3.Connection, case_id: int, code: str | None) -> str | None:
    """Oznacza odpowiedź wydziału. Bez wskazanego wydziału — jeśli czeka tylko jeden, to on odpowiedział."""
    if not code:
        waiting = [r[0] for r in conn.execute(
            "SELECT code FROM case_departments WHERE case_id = ? AND status != ?", (case_id, ANSWERED))]
        if len(waiting) != 1:
            return None
        code = waiting[0]
    conn.execute(
        "INSERT OR IGNORE INTO case_departments(case_id, code, status) VALUES (?, ?, ?)", (case_id, code, PENDING)
    )
    conn.execute(
        "UPDATE case_departments SET status = ?, answered_at = ? WHERE case_id = ? AND code = ?",
        (ANSWERED, date.today().isoformat(), case_id, code),
    )
    _sync_case_field(conn, case_id)
    return code


def set_status(conn: sqlite3.Connection, case_id: int, code: str, status: str, note: str | None = None) -> None:
    answered = date.today().isoformat() if status == ANSWERED else None
    extra = ", clarification_count = clarification_count + 1" if status == CLARIFICATION else ""
    conn.execute(
        f"UPDATE case_departments SET status = ?, answered_at = ?, note = COALESCE(?, note){extra} WHERE case_id = ? AND code = ?",
        (status, answered, note, case_id, code),
    )


def _sync_case_field(conn: sqlite3.Connection, case_id: int) -> None:
    """Pole cases.departments odzwierciedla wszystkie wydziały z ewidencji (np. dodane przy odpowiedzi)."""
    codes = [r[0] for r in conn.execute("SELECT code FROM case_departments WHERE case_id = ? ORDER BY rowid", (case_id,))]
    conn.execute("UPDATE cases SET departments = ? WHERE id = ?", (json.dumps(codes, ensure_ascii=False), case_id))


def for_case(conn: sqlite3.Connection, case_id: int) -> list[dict]:
    names = {r["code"]: r["name"] for r in conn.execute("SELECT code, name FROM departments")}
    rows = conn.execute("SELECT * FROM case_departments WHERE case_id = ? ORDER BY rowid", (case_id,)).fetchall()
    return [
        {
            "code": r["code"],
            "name": names.get(r["code"], r["code"]),
            "status": r["status"],
            "status_label": STATUS_LABELS.get(r["status"], r["status"]),
            "requested_at": r["requested_at"],
            "answered_at": r["answered_at"],
            "clarification_count": r["clarification_count"],
            "note": r["note"],
        }
        for r in rows
    ]


def summary(conn: sqlite3.Connection) -> dict[int, dict]:
    """Podsumowanie do listy spraw: {case_id: {total, answered, waiting: [kody], clarification: [kody]}}."""
    out: dict[int, dict] = {}
    for r in conn.execute("SELECT case_id, code, status FROM case_departments ORDER BY rowid"):
        s = out.setdefault(r["case_id"], {"total": 0, "answered": 0, "waiting": [], "clarification": []})
        s["total"] += 1
        if r["status"] == ANSWERED:
            s["answered"] += 1
        elif r["status"] == CLARIFICATION:
            s["clarification"].append(r["code"])
        else:
            s["waiting"].append(r["code"])
    return out


def clarification_request(case: dict, dept_name: str, details: str | None, previous_answer: str | None) -> str:
    """Treść prośby do wydziału o uszczegółowienie odpowiedzi — urzędnik kopiuje i wysyła sam."""
    received = case.get("received_date") or ""
    try:
        received = date.fromisoformat(received).strftime("%d.%m.%Y")
    except ValueError:
        pass
    scope = (details or "").strip() or "[DO UZUPEŁNIENIA: czego brakuje w odpowiedzi]"
    deadline = case.get("deadline_date") or ""
    try:
        deadline = date.fromisoformat(deadline).strftime("%d.%m.%Y")
    except ValueError:
        pass
    parts = [
        "Szanowny Panie Dyrektorze / Szanowna Pani Dyrektor,",
        f"w nawiązaniu do przekazanych materiałów w sprawie wniosku o udostępnienie informacji publicznej "
        f"z dnia {received} r. (znak sprawy: {case.get('case_number')}), dotyczącego: {case.get('subject')}, "
        f"uprzejmie proszę o uszczegółowienie odpowiedzi przekazanej przez {dept_name} w zakresie:",
        scope,
        f"Termin udzielenia odpowiedzi wnioskodawcy upływa {deadline} r., dlatego proszę o przekazanie uzupełnienia "
        "w możliwie najkrótszym terminie, a w razie braku takiej możliwości — o informację o przewidywanym terminie "
        "(§ 11 ust. 5 Zarządzenia nr 535/2024).",
        "Z poważaniem",
    ]
    if previous_answer:
        parts.insert(3, f"Dotychczas przekazano: „{previous_answer.strip()[:400]}{'…' if len(previous_answer) > 400 else ''}”")
    return "\n\n".join(parts)
