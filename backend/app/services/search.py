"""Wyszukiwanie w archiwum (FTS5, ranking BM25) i podpowiedzi komórek właściwych dla wniosku."""
import re
import sqlite3
from collections import Counter

from services import dept_tracking
from services.patterns import PL_LETTER

# Słowa bez wartości wyszukiwawczej: formuły pism UDIP i polskie słowa funkcyjne.
STOPWORDS = frozenset(
    """
    oraz albo lub czy jest są był była było były będzie będą jako jaki jaka jakie jakich jakim który która które
    których którym tego tej ten tych tym temu także również przez przy przed pod nad dla bez od do na za po
    się nie tak też jego jej ich nich mnie mój moja moje nasz nasza wasz proszę prosze uprzejmie zwracam
    wniosek wniosku wnioskiem wnioskodawca informacji informacja informację informacje publicznej publiczna publiczną
    udostępnienie udostępnienia udostępnić podstawie ustawy ustawa art dnia roku rok lata latach szanowni
    państwo panie pani pana urząd urzędu miasta miasto bydgoszczy bydgoszcz prezydent odpowiedź odpowiedzi
    poprzez celu sprawie dotyczy dotyczące dotyczących dotyczącej wraz ktore ilu ile kiedy gdzie
    email mail adres adresem przesłanie przesłania formie elektronicznej pozdrawiam dziękuję dziekuje
    """.split()
)
WORD = re.compile(f"[0-9{PL_LETTER}]{{3,}}")

# Prosty „stemming” polskiej fleksji: prefiks słowa (remont, remontu, remontem → remont*).
STEM_LENGTH = 6
QUERY_WORDS = 24
RULE_QUERY_WORDS = 16

# Wagi BM25 kolumn cases_fts: znak sprawy, wnioskodawca, temat z treścią wniosku, odpowiedź, wydziały.
CASE_COLUMN_WEIGHTS = (2.0, 0.5, 4.0, 1.5, 0.5)
# Podobna sprawa musi mieć co najmniej 25% trafności najlepszej — odcina trafienia po jednym wspólnym słowie.
MIN_RELATIVE_SCORE = 0.25

LLM_SUGGESTION_WEIGHT = 3.0
SIMILAR_CASE_WEIGHT = 2.0
MAX_KEYWORD_HITS = 3
# Wydział z wynikiem poniżej 35% najlepszego to szum (pojedyncze przypadkowe słowo kluczowe).
SUGGESTION_NOISE_RATIO = 0.35


def _is_meaningful(word: str) -> bool:
    return len(word) == 4 if word.isdigit() else word not in STOPWORDS


def keywords(text: str, limit: int = QUERY_WORDS) -> list[str]:
    words = (word.lower() for word in WORD.findall(text or ""))
    return [word for word, _ in Counter(word for word in words if _is_meaningful(word)).most_common(limit)]


def stem(word: str) -> str:
    return word[:STEM_LENGTH]


def _fts_term(word: str) -> str:
    word = word.replace('"', "")
    return f'"{word}"' if word.isdigit() else f'"{stem(word)}"*'


def match_any_word(text: str, limit: int = QUERY_WORDS) -> str | None:
    words = keywords(text, limit)
    return " OR ".join(_fts_term(word) for word in words) if words else None


def match_all_words(query: str) -> str | None:
    """Zapytanie z paska wyszukiwania rejestru — wszystkie słowa muszą wystąpić."""
    words = [word.lower() for word in WORD.findall(query or "")] or (query or "").split()
    return " AND ".join(_fts_term(word) for word in words) if words else None


def similar_cases(conn: sqlite3.Connection, text: str, limit: int = 5, exclude_id: int | None = None) -> list[dict]:
    match = match_any_word(text)
    if not match:
        return []
    rows = conn.execute(
        f"""
        SELECT c.id, c.case_number, c.received_date, c.response_date, c.applicant, c.subject, c.procedure_mode,
               coalesce(c.response_text, '') AS response_text,
               bm25(cases_fts, {', '.join(map(str, CASE_COLUMN_WEIGHTS))}) AS bm25_score
        FROM cases_fts JOIN cases c ON c.id = cases_fts.rowid
        WHERE cases_fts MATCH ? AND (? IS NULL OR c.id != ?)
        ORDER BY bm25_score
        LIMIT ?
        """,
        (match, exclude_id, exclude_id, limit),
    ).fetchall()
    if not rows:
        return []
    dept_rows = dept_tracking.rows_by_case(conn, ",".join(str(row["id"]) for row in rows))
    results = [
        {
            **{key: row[key] for key in row.keys() if key != "bm25_score"},
            "departments": [dept["code"] for dept in dept_rows.get(row["id"], [])],
            # BM25 w SQLite jest ujemny (im mniejszy, tym lepiej) — odwracamy znak, żeby „więcej” znaczyło „bardziej podobna”.
            "score": round(-row["bm25_score"], 4) if row["bm25_score"] else None,
        }
        for row in rows
    ]
    best = max((result["score"] or 0 for result in results), default=0)
    if best > 0:
        results = [result for result in results if (result["score"] or 0) >= best * MIN_RELATIVE_SCORE]
    return results


def relevant_rules(conn: sqlite3.Connection, text: str, limit: int = 4) -> list[dict]:
    """Przepisy pasujące do sprawy; bez trafień — pierwsze aktywne (podstawowe przepisy u.d.i.p.)."""
    match = match_any_word(text, RULE_QUERY_WORDS)
    rows = []
    if match:
        rows = conn.execute(
            """
            SELECT r.id, r.title, r.source, r.content FROM rules_fts JOIN rules r ON r.id = rules_fts.rowid
            WHERE rules_fts MATCH ? AND r.is_active ORDER BY bm25(rules_fts) LIMIT ?
            """,
            (match, limit),
        ).fetchall()
    if not rows:
        rows = conn.execute("SELECT id, title, source, content FROM rules WHERE is_active ORDER BY id LIMIT ?", (limit,)).fetchall()
    return [dict(row) for row in rows]


def _keyword_hits(keywords_csv: str, text: str, *, whole_word: bool) -> list[str]:
    hits = []
    for keyword in (part.strip().lower() for part in keywords_csv.split(",")):
        stemmed = " ".join(stem(word) for word in keyword.split())
        if not stemmed:
            continue
        found = re.search(r"\b" + re.escape(stemmed), text) if whole_word else stemmed in text
        if found:
            hits.append(keyword)
    return hits


def suggest_departments(
    text: str,
    similar: list[dict],
    active_departments: list[dict],
    llm_suggestions: list[dict] | None = None,
    limit: int = 3,
) -> list[dict]:
    """Łączy trzy źródła: wskazania modelu, wydziały z podobnych spraw i słowa kluczowe wydziałów."""
    by_code = {dept["code"]: dept for dept in active_departments}
    scores: Counter = Counter()
    reasons: dict[str, list[str]] = {}

    def add(code: str, score: float, reason: str) -> None:
        if code not in by_code:
            return
        scores[code] += score
        code_reasons = reasons.setdefault(code, [])
        if reason and reason not in code_reasons:
            code_reasons.append(reason)

    for suggestion in llm_suggestions or []:
        add(str(suggestion.get("code", "")).strip().upper(), LLM_SUGGESTION_WEIGHT, str(suggestion.get("reason") or "").strip())
    for rank, case in enumerate(similar):
        for code in case["departments"]:
            add(code, SIMILAR_CASE_WEIGHT / (rank + 1), f"analogiczna sprawa {case['case_number']}")
    lowered = (text or "").lower()
    for code, dept in by_code.items():
        hits = _keyword_hits(dept["keywords"], lowered, whole_word=False)
        if hits:
            add(code, min(len(hits), MAX_KEYWORD_HITS), "zakres tematyczny: " + ", ".join(hits[:MAX_KEYWORD_HITS]))

    top = max(scores.values(), default=0)
    suggestions = []
    for code, score in scores.most_common(limit):
        if score < top * SUGGESTION_NOISE_RATIO:
            continue
        reason = "; ".join(reasons[code]) or "zbieżność tematyczna"
        suggestions.append({"code": code, "name": by_code[code]["name"], "reason": reason[0].upper() + reason[1:]})
    return suggestions


def suggest_external_entities(conn: sqlite3.Connection, text: str, limit: int = 2) -> list[dict]:
    """Podmioty spoza UMB (z pism „nie jest dysponentem”), których słowa kluczowe występują we wniosku."""
    lowered = (text or "").lower()
    found = []
    for row in conn.execute("SELECT id, name, keywords FROM external_entities WHERE is_active"):
        hits = _keyword_hits(row["keywords"], lowered, whole_word=True)
        if hits:
            found.append((len(hits), {"id": row["id"], "name": row["name"], "reason": "Słowa kluczowe: " + ", ".join(hits[:MAX_KEYWORD_HITS])}))
    found.sort(key=lambda entry: -entry[0])
    return [entity for _, entity in found[:limit]]
