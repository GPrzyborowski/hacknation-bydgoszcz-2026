"""Wyszukiwanie podobnych spraw (cases_fts) i reguł (rules_fts) + podpowiedzi wydziałów."""
import json
import re
import sqlite3
from collections import Counter

import db

# Słowa bez wartości wyszukiwawczej (formuły pism UDIP i polskie słowa funkcyjne).
STOPWORDS = set(
    """
    oraz albo lub czy jest są był była było były będzie będą jako jaki jaka jakie jakich jakim który która które
    których którym tego tej ten tych tym temu także również przez przy przed pod nad dla bez od do na za po
    się nie tak też jego jej ich nich mnie mój moja moje nasz nasza wasz proszę prosze uprzejmie zwracam zwracam się
    wniosek wniosku wnioskiem wnioskodawca informacji informacja informację informacje publicznej publiczna publiczną
    udostępnienie udostępnienia udostępnić podstawie ustawy ustawa art dnia roku rok lata latach szanowni
    państwo panie pani pana urząd urzędu miasta miasto bydgoszczy bydgoszcz prezydent odpowiedź odpowiedzi
    poprzez celu sprawie dotyczy dotyczące dotyczących dotyczącej wraz które ktore jakie ilu ile kiedy gdzie
    email mail adres adresem przesłanie przesłania formie elektronicznej pozdrawiam dziękuję dziekuje
    """.split()
)

WORD_RE = re.compile(r"[0-9A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż]{3,}")


def keywords(text: str, limit: int = 24) -> list[str]:
    words = [w.lower() for w in WORD_RE.findall(text or "")]
    counts = Counter(w for w in words if w not in STOPWORDS and not w.isdigit() or (w.isdigit() and len(w) == 4))
    return [w for w, _ in counts.most_common(limit)]


def _fts_term(word: str) -> str:
    # Prosty "stemming" dla polskiej fleksji: prefiks słowa z gwiazdką (remont, remontu, remontem → remon*).
    word = word.replace('"', "")
    if word.isdigit():
        return f'"{word}"'
    stem = word[:6] if len(word) > 6 else word
    return f'"{stem}"*'


def fts_query(text: str, limit: int = 24) -> str | None:
    words = keywords(text, limit)
    if not words:
        return None
    return " OR ".join(_fts_term(w) for w in words)


def similar_cases(
    conn: sqlite3.Connection, text: str, limit: int = 5, exclude_id: int | None = None, min_relative_score: float = 0.25
) -> list[dict]:
    """Najbardziej podobne sprawy archiwalne — ranking BM25 (FTS5) lub LIKE, gdy FTS5 niedostępne."""
    rows: list[sqlite3.Row] = []
    if db.FTS_ENABLED:
        query = fts_query(text)
        if not query:
            return []
        rows = conn.execute(
            """
            SELECT c.*, bm25(cases_fts, 2.0, 0.5, 4.0, 1.5, 0.5) AS score
            FROM cases_fts JOIN cases c ON c.id = cases_fts.rowid
            WHERE cases_fts MATCH ? AND (? IS NULL OR c.id != ?)
            ORDER BY score
            LIMIT ?
            """,
            (query, exclude_id, exclude_id, limit),
        ).fetchall()
    else:
        words = keywords(text, 8)
        if not words:
            return []
        clause = " OR ".join("(c.subject LIKE ? OR c.response_text LIKE ?)" for _ in words)
        params: list = []
        for w in words:
            params += [f"%{w[:6]}%", f"%{w[:6]}%"]
        rows = conn.execute(
            f"SELECT c.*, 0 AS score FROM cases c WHERE ({clause}) AND (? IS NULL OR c.id != ?) ORDER BY c.received_date DESC LIMIT ?",
            (*params, exclude_id, exclude_id, limit),
        ).fetchall()
    results = [similar_case_dict(r) for r in rows]
    # Odcinamy przypadkowe trafienia (np. pojedyncze wspólne słowo): min. 25% trafności najlepszego wyniku.
    best = max((r["score"] or 0 for r in results), default=0)
    if best > 0:
        results = [r for r in results if (r["score"] or 0) >= best * min_relative_score]
    return results


def similar_case_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "case_number": row["case_number"],
        "received_date": row["received_date"],
        "response_date": row["response_date"],
        "applicant": row["applicant"],
        "subject": row["subject"],
        "procedure_mode": row["procedure_mode"],
        "departments": json.loads(row["departments"] or "[]"),
        "response_text": row["response_text"] or "",
        "score": round(-float(row["score"]), 4) if row["score"] else None,
    }


def search_case_ids(conn: sqlite3.Connection, q: str) -> list[int] | None:
    """Identyfikatory spraw pasujących do frazy z paska wyszukiwania (wszystkie słowa muszą wystąpić)."""
    words = [w.lower() for w in WORD_RE.findall(q or "")] or [w for w in (q or "").split() if w]
    if not words:
        return None
    if db.FTS_ENABLED:
        query = " AND ".join(_fts_term(w) for w in words)
        return [r[0] for r in conn.execute("SELECT rowid FROM cases_fts WHERE cases_fts MATCH ?", (query,)).fetchall()]
    clause = " AND ".join("(case_number || ' ' || applicant || ' ' || subject || ' ' || coalesce(response_text,'')) LIKE ?" for _ in words)
    return [r[0] for r in conn.execute(f"SELECT id FROM cases WHERE {clause}", [f"%{w}%" for w in words]).fetchall()]


def relevant_rules(conn: sqlite3.Connection, text: str, limit: int = 4) -> list[dict]:
    rows: list[sqlite3.Row] = []
    if db.FTS_ENABLED:
        query = fts_query(text, 16)
        if query:
            rows = conn.execute(
                """
                SELECT r.id, r.title, r.source, r.content FROM rules_fts JOIN rules r ON r.id = rules_fts.rowid
                WHERE rules_fts MATCH ? AND r.is_active = 1 ORDER BY bm25(rules_fts) LIMIT ?
                """,
                (query, limit),
            ).fetchall()
    if not rows:
        rows = conn.execute(
            "SELECT id, title, source, content FROM rules WHERE is_active = 1 ORDER BY id LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def departments(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT code, name, keywords FROM departments WHERE is_active = 1 ORDER BY code")]


def suggest_departments(
    conn: sqlite3.Connection,
    text: str,
    similar: list[dict],
    llm_suggestions: list[dict] | None = None,
    limit: int = 3,
) -> list[dict]:
    """Łączy trzy źródła: wskazania LLM, wydziały z podobnych spraw i słowa kluczowe wydziałów."""
    depts = {d["code"]: d for d in departments(conn)}
    scores: Counter = Counter()
    reasons: dict[str, list[str]] = {}

    def add(code: str, score: float, reason: str) -> None:
        if code not in depts:
            return
        scores[code] += score
        reasons.setdefault(code, [])
        if reason and reason not in reasons[code]:
            reasons[code].append(reason)

    for s in llm_suggestions or []:
        code = str(s.get("code", "")).strip().upper()
        add(code, 3.0, str(s.get("reason") or "").strip())

    for rank, case in enumerate(similar):
        weight = 2.0 / (rank + 1)
        for code in case["departments"]:
            add(code, weight, f"analogiczna sprawa {case['case_number']}")

    lowered = (text or "").lower()
    for code, dept in depts.items():
        hits = []
        for kw in (k.strip().lower() for k in dept["keywords"].split(",")):
            if not kw:
                continue
            stem = " ".join(part[:6] if len(part) > 6 else part for part in kw.split())
            if stem and stem in lowered:
                hits.append(kw)
        if hits:
            add(code, 1.0 * min(len(hits), 3), "zakres tematyczny: " + ", ".join(hits[:3]))

    result = []
    top = max(scores.values(), default=0)
    for code, score in scores.most_common(limit):
        if score < top * 0.35:  # pojedyncze przypadkowe słowo kluczowe obok mocnych wskazań to szum
            continue
        reason = "; ".join(reasons[code]) or "zbieżność tematyczna"
        result.append({"code": code, "name": depts[code]["name"], "reason": reason[0].upper() + reason[1:]})
    return result


def suggest_external_entities(conn: sqlite3.Connection, text: str, limit: int = 2) -> list[dict]:
    """Podmioty spoza UMB (z pism „nie jest dysponentem”), których słowa kluczowe występują we wniosku."""
    lowered = (text or "").lower()
    found = []
    for row in conn.execute("SELECT id, name, keywords FROM external_entities WHERE is_active = 1"):
        hits = []
        for kw in (k.strip().lower() for k in row["keywords"].split(",")):
            stem = " ".join(part[:6] if len(part) > 6 else part for part in kw.split())
            if stem and re.search(r"\b" + re.escape(stem), lowered):
                hits.append(kw)
        if hits:
            found.append((len(hits), {"id": row["id"], "name": row["name"], "reason": "Słowa kluczowe: " + ", ".join(hits[:3])}))
    found.sort(key=lambda x: -x[0])
    return [f for _, f in found[:limit]]
