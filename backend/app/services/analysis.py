"""Zadania modelu językowego: przetworzenie wniosku i projekt odpowiedzi. Bez modelu — analiza regułowa."""
import logging
import re
from collections.abc import Callable
from functools import cached_property
from string import Template
from typing import TypeVar

import config
from schemas import ParsedRequest
from services import letters, llm
from services.deadlines import parse_date
from services.patterns import EMAIL, PL_LOWER, PL_UPPER, STREET_PREFIX

log = logging.getLogger(__name__)

T = TypeVar("T")

PROMPT_TEXT_CHARS = 12000
PROMPT_REQUEST_CHARS = 4000
PROMPT_RULE_CHARS = 600
PROMPT_EXAMPLE_CHARS = 2500
SUBJECT_MAX_CHARS = 160
MAX_QUESTIONS = 15
APPLICANT_MAX_CHARS = 120

CATEGORIES = [
    "inwestycje", "finanse i budżet", "zamówienia publiczne", "nieruchomości", "budownictwo", "edukacja",
    "sport", "kultura", "środowisko", "gospodarka odpadami", "transport i drogi", "zatrudnienie i kadry",
    "rada miasta", "promocja", "zdrowie i pomoc społeczna", "podatki i opłaty", "organizacja urzędu", "inne",
]
APPLICANT_TYPES = ["osoba fizyczna", "organizacja", "dziennikarz", "przedsiębiorca", "radny", "inny"]


def _with_fallback(call: Callable[[], T], fallback: Callable[[str | None], T]) -> T:
    """Wynik modelu albo wynik regułowy: bez klucza API (powód None) lub gdy Gemini zawiódł, a zapas jest włączony."""
    try:
        return call()
    except llm.LLMDisabled:
        return fallback(None)
    except llm.LLMError as exc:
        if not config.LLM_FALLBACK_HEURISTIC:
            raise
        log.warning("Gemini niedostępny, używam analizy regułowej: %s", exc.message)
        return fallback(exc.message)


# --- przetworzenie wniosku -----------------------------------------------------------------------

PARSE_PROMPT = Template("""Jesteś asystentem urzędnika Urzędu Miasta Bydgoszczy obsługującego wnioski o udostępnienie informacji publicznej (u.d.i.p.).
Z treści wniosku wyodrębnij dane i zwróć WYŁĄCZNIE obiekt JSON o kluczach:
- "wnioskodawca": imię i nazwisko lub nazwa wnioskodawcy albo null,
- "typ_wnioskodawcy": jedno z: $types albo null,
- "adres_do_odpowiedzi": e-mail lub adres korespondencyjny albo null,
- "forma_odpowiedzi": "email", "e-Doręczenia", "poczta", "odbiór osobisty", "ePUAP" albo "nieokreślona",
- "data_na_pismie": data pisma w formacie RRRR-MM-DD albo null,
- "temat_skrot": zwięzłe streszczenie przedmiotu wniosku (do 12 słów),
- "pytania": lista wszystkich pytań/żądań wnioskodawcy, każde jako osobny string, bez parafrazowania sensu,
- "kategoria": jedno z: $categories,
- "czy_to_wniosek_udip": true jeśli to wniosek o informację publiczną, false jeśli np. skarga, petycja, wniosek w trybie KPA,
- "uwagi": krótkie uwagi analityczne: czy to informacja przetworzona (art. 3 ust. 1 pkt 1), braki formalne, czy dotyczy danych osobowych, czy UMB może nie być dysponentem,
- "sugerowane_wydzialy": lista maks. 3 obiektów {"code": symbol z listy, "reason": krótkie uzasadnienie}.
Lista komórek UMB (symbol – nazwa – zakres):
$departments
Nie wymyślaj danych, których nie ma we wniosku — wtedy wpisz null.""")


def parse_request(text: str, departments: list[dict]) -> tuple[dict, list[dict], bool]:
    """Zwraca (przetworzone zgłoszenie, wydziały wskazane przez model, czy użyto modelu)."""

    def with_model() -> tuple[dict, list[dict], bool]:
        system = PARSE_PROMPT.substitute(
            types=", ".join(APPLICANT_TYPES),
            categories=", ".join(CATEGORIES),
            departments="\n".join(f"{d['code']} – {d['name']} – {d['keywords']}" for d in departments),
        )
        data = llm.chat_json(system, f'TREŚĆ WNIOSKU:\n"""\n{text[:PROMPT_TEXT_CHARS]}\n"""')
        return _normalize_parsed(data, text), list(data.get("sugerowane_wydzialy") or []), True

    def without_model(failure: str | None) -> tuple[dict, list[dict], bool]:
        parsed = heuristic_parse(text)
        if failure:
            parsed["uwagi"] = f"Model językowy niedostępny ({failure}) — użyto analizy heurystycznej. " + parsed["uwagi"]
        return parsed, [], False

    return _with_fallback(with_model, without_model)


class _LazyHeuristic:
    """Wynik analizy regułowej liczony dopiero wtedy, gdy model czegoś nie uzupełnił."""

    def __init__(self, text: str):
        self._text = text

    @cached_property
    def result(self) -> dict:
        return heuristic_parse(self._text)

    def __getitem__(self, key: str):
        return self.result[key]


def _normalize_parsed(data: dict, text: str) -> dict:
    fallback = _LazyHeuristic(text)
    parsed = {key: (None if data.get(key) in ("", "null", "brak") else data.get(key)) for key in ParsedRequest.model_fields}

    questions = parsed["pytania"]
    if isinstance(questions, str):
        questions = [questions]
    parsed["pytania"] = [str(q).strip() for q in questions or [] if str(q).strip()] or fallback["pytania"]
    parsed["temat_skrot"] = str(parsed["temat_skrot"] or fallback["temat_skrot"])
    parsed["kategoria"] = str(parsed["kategoria"] or fallback["kategoria"])
    parsed["uwagi"] = str(parsed["uwagi"] or "")
    is_udip = parsed["czy_to_wniosek_udip"]
    parsed["czy_to_wniosek_udip"] = is_udip if isinstance(is_udip, bool) else str(is_udip).lower() in {"true", "tak", "1"}
    if parsed["data_na_pismie"]:
        letter_date, _ = parse_date(parsed["data_na_pismie"])
        parsed["data_na_pismie"] = letter_date.isoformat() if letter_date else None
    for key in ("wnioskodawca", "typ_wnioskodawcy", "adres_do_odpowiedzi", "forma_odpowiedzi"):
        parsed[key] = str(parsed[key]).strip() if parsed[key] is not None else fallback[key]
    return parsed


# --- analiza regułowa ------------------------------------------------------------------------------

_EMAIL = re.compile(EMAIL)
_ADDRESS = re.compile(rf"{STREET_PREFIX}\s*[^\n,]{{2,40}}\d+[a-zA-Z]?(?:/\d+)?(?:,?\s*\d{{2}}-\d{{3}}\s+\w+)?", re.IGNORECASE)
_PERSON = re.compile(rf"(?:[{PL_UPPER}][{PL_LOWER}]+|[{PL_UPPER}]\.)(?:[ -][{PL_UPPER}][{PL_LOWER}]+){{1,2}}")
_ORGANIZATION = re.compile(
    rf"((?:Stowarzyszenie|Fundacja|Parafia|Redakcja|Proboszcz Parafii|Spółdzielnia|Towarzystwo)\s[^,\n]{{3,80}}"
    rf"|[{PL_UPPER}][\w-]+(?:\s[{PL_UPPER}][\w-]+)*\s(?:S\.A\.|sp\. z o\.o\.|Sp\. z o\.o\.))"
)
_CLOSING = re.compile(r"^(?:--\s*)?(?:pozdrawiam|z poważaniem|z wyrazami szacunku|łączę wyrazy szacunku|z wyrazami)\b[\s|,]*", re.IGNORECASE)
_SIGNATURE_MAX_CHARS = 70
_LIST_MARKER = re.compile(r"^(\d+[.)]|[a-z][.)]|[-•–])\s+")
_SUBJECT_PREFIX = re.compile(r"^(dotyczy|dot\.|w sprawie|temat)\s*:?\s*", re.IGNORECASE)

_CATEGORY_KEYWORDS = {
    "środowisko": ["zwierz", "drzew", "środowisk", "zieleń"],
    "gospodarka odpadami": ["odpad", "śmieci", "śmieć"],
    "inwestycje": ["inwestyc", "remont", "przebudow", "budow"],
    "zamówienia publiczne": ["przetarg", "zamówieni", "wykonawc"],
    "finanse i budżet": ["budżet", "wydatk", "koszt", "kwot"],
    "nieruchomości": ["nieruchomoś", "działk", "dzierżaw", "najem"],
    "zatrudnienie i kadry": ["zatrudni", "wynagrodz", "etat", "pracownik"],
    "edukacja": ["szkoł", "przedszkol", "oświat"],
    "kultura": ["kultur", "teatr", "festiwal", "rzeźb", "pomnik", "zabyt"],
    "promocja": ["promocj", "reklam"],
    "rada miasta": ["radn", "rada miasta", "sesj"],
}


def _organization(text: str) -> str | None:
    match = _ORGANIZATION.search(text)
    return match.group(1).strip() if match else None


def _applicant(text: str, lines: list[str]) -> str | None:
    """Wnioskodawca wg wzorców z wniosków testowych UMB: pole „Wnioskodawca:”, podpis po formule grzecznościowej
    („Pozdrawiam | Ewa Góra”, „E. Góra”), nazwa organizacji na końcu albo w pierwszym zdaniu, wreszcie adres e-mail."""
    labelled = re.search(r"(?:wnioskodawca|imię i nazwisko)\s*[:\-]\s*(.+)", text, re.IGNORECASE)
    if labelled:
        return labelled.group(1).strip()[:APPLICANT_MAX_CHARS]

    tail = [line for line in lines[-8:] if line.strip("- ")]
    for index, line in enumerate(tail):
        if not _CLOSING.match(line):
            continue
        rest = _CLOSING.sub("", line).strip(" |")
        for candidate in [rest] if rest else tail[index + 1 : index + 3]:
            if organization := _organization(candidate):
                return organization
            if _PERSON.fullmatch(candidate.strip()):
                return candidate.strip()
    for line in reversed(tail):
        if len(line) < _SIGNATURE_MAX_CHARS and (organization := _organization(line)):
            return organization
        if _PERSON.fullmatch(line.strip()):
            return line.strip()
    for line in lines[:6]:
        if match := _ORGANIZATION.match(line):
            return match.group(1).strip().rstrip(",")
    # Wniosek mailowy bez podpisu — rejestr UMB wpisuje wtedy adres e-mail (sprawa BKS.IV.1431.17.2026).
    email = _EMAIL.search(text)
    return email.group(0) if email else None


def _questions(text: str, lines: list[str]) -> list[str]:
    questions = []
    for line in lines:
        if line.endswith("?") or _LIST_MARKER.match(line):
            question = _LIST_MARKER.sub("", line)
            if len(question) > 8:
                questions.append(question)
    if not questions:
        request = re.search(
            r"(?:proszę o|wnoszę o|wnioskuję o|zwracam się z (?:uprzejmą )?prośbą o)\s+(.{10,400}?)(?:\.|$)",
            text, re.IGNORECASE | re.DOTALL,
        )
        if request:
            questions.append(" ".join(request.group(1).split()))
    return questions[:MAX_QUESTIONS]


def _subject(lines: list[str], questions: list[str]) -> str:
    # „Temat:” z nagłówka e-maila bywa pusty (wniosek BKS.IV.1431.543.2026), więc wymagamy treści po prefiksie.
    labelled = next((line for line in lines if re.match(r"^(dotyczy|dot\.|w sprawie|temat)\b\s*:?\s*\S.{8,}", line, re.IGNORECASE)), None)
    if labelled:
        return _SUBJECT_PREFIX.sub("", labelled)
    scope = re.search(
        r"informacji publicznej\s+(?:w zakresie|na temat|dotycząc\w*|dot\.)\s+(.{10,200}?)(?:[.:;]|\s+z następujących|$)",
        " ".join(lines), re.IGNORECASE,
    )
    if scope:
        return scope.group(1)
    if questions:
        return questions[0]
    meaningful = [line for line in lines if len(line) > 25 and not re.match(r"^(dzień dobry|witam|szanown|biuro|urząd)", line, re.IGNORECASE)]
    return meaningful[0] if meaningful else (lines[0] if lines else "")


def _reply_form(lowered: str) -> str:
    if "e-doręcze" in lowered or "e-dorecze" in lowered:
        return "e-Doręczenia"
    if "e-mail" in lowered or "mail" in lowered or "elektroniczn" in lowered:
        return "email"
    if "poczt" in lowered or "listown" in lowered:
        return "poczta"
    if "epuap" in lowered:
        return "ePUAP"
    return "nieokreślona"


def _applicant_type(lowered: str, applicant: str | None) -> str | None:
    if any(marker in lowered for marker in ("redakc", "dziennikar", "gazet", "portal")):
        return "dziennikarz"
    if applicant and _ORGANIZATION.search(applicant):
        return "organizacja"
    if re.search(r"\b(fundacja|stowarzyszenie|spółdzielnia|parafia)\b", lowered[:300]):
        return "organizacja"
    return "osoba fizyczna" if applicant else None


def _category(lowered: str) -> str:
    for category, stems in _CATEGORY_KEYWORDS.items():
        if any(re.search(r"\b" + re.escape(stem), lowered) for stem in stems):
            return category
    return "inne"


def heuristic_parse(text: str) -> dict:
    """Ekstrakcja regułowa — działa bez modelu językowego (tryb bez klucza i zapas przy awarii Gemini)."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    lowered = text.lower()
    email = _EMAIL.search(text)
    address = _ADDRESS.search(text)
    applicant = _applicant(text, lines)
    questions = _questions(text, lines)

    letter_date = None
    for line in lines[:12]:
        if re.search(r"\b(dnia|dn\.|\d{1,2}[./-]\d{1,2}[./-]\d{4}|\d{4}-\d{2}-\d{2})", line):
            parsed, _ = parse_date(line)
            if parsed:
                letter_date = parsed.isoformat()
                break

    notes = []
    if not any(phrase in lowered for phrase in ("informacji publicznej", "u.d.i.p", "dostępie do informacji")):
        notes.append("Brak wprost powołania się na u.d.i.p. — zweryfikuj tryb.")
    if re.search(r"zestawieni|analiz|wylicz|porównani|sumaryczn", lowered):
        notes.append("Możliwa informacja przetworzona (art. 3 ust. 1 pkt 1 u.d.i.p.).")
    if not (email or address):
        notes.append("Brak adresu do odpowiedzi.")
    notes.append("Analiza heurystyczna (bez modelu językowego) — sprawdź dane.")

    return {
        "wnioskodawca": applicant,
        "typ_wnioskodawcy": _applicant_type(lowered, applicant),
        "adres_do_odpowiedzi": email.group(0) if email else (address.group(0).strip() if address else None),
        "forma_odpowiedzi": _reply_form(lowered),
        "data_na_pismie": letter_date,
        "temat_skrot": _subject(lines, questions)[:SUBJECT_MAX_CHARS],
        "pytania": questions,
        "kategoria": _category(lowered),
        "czy_to_wniosek_udip": "informac" in lowered and "publiczn" in lowered,
        "uwagi": " ".join(notes),
    }


# --- projekt odpowiedzi ------------------------------------------------------------------------------

DRAFT_PROMPT = Template("""Jesteś asystentem urzędnika Biura Komunikacji Społecznej Urzędu Miasta Bydgoszczy. Przygotuj PROJEKT pisma — odpowiedzi na wniosek o udostępnienie informacji publicznej — w stylu pism BKS UMB.
Układ pisma (bez nagłówka urzędu, daty, znaku sprawy i podpisu — te dodaje system):
1. Zwrot: "$salutation"
2. Akapit otwierający, np.: "w odpowiedzi na wystosowany $by wniosek o udostępnienie informacji publicznej w zakresie <zakres>, na podstawie materiału przygotowanego przez komórkę merytoryczną, tj. <nazwa wydziału> Urzędu Miasta Bydgoszczy informuję, co następuje."
3. Odpowiedzi kolejno na pytania, każda poprzedzona wierszem "Ad 1", "Ad 2"... (przy jednym pytaniu bez numeracji). Ewentualnie "Załącznik:" z listą załączników.
4. Zakończenie: "Łączę wyrazy szacunku,"
Zasady:
- Opieraj się WYŁĄCZNIE na materiałach przekazanych przez wydziały. Nie dopisuj faktów, kwot, dat ani nazw, których tam nie ma.
- Jeśli materiały nie odpowiadają na któreś pytanie, wstaw znacznik [DO UZUPEŁNIENIA: ...].
- Jeśli wydział informuje, że nie posiada informacji lub nie prowadzi statystyk — napisz to wprost (jak w archiwalnych pismach).
- Uwzględnij przepisy z sekcji PRZEPISY, jeśli mają zastosowanie (informacja przetworzona, ochrona prywatności, BIP).
- Wzoruj się na stylu WZORU Z ARCHIWUM, ale nie kopiuj jego faktów.
Wskaż też fragmenty projektu wymagające anonimizacji: dane osób prywatnych niepełniących funkcji publicznych i inne kategorie z listy. NIE wskazuj danych urzędów, jednostek miejskich ani osób pełniących funkcje publiczne w związku z ich funkcją.
Zwróć WYŁĄCZNIE JSON: {"draft_text": "...", "anonymization_candidates": [{"quote": "dokładny cytat z draft_text", "category": "...", "reason": "..."}]}
Kategorie anonimizacji (wg listy UMB): $categories""")


def _draft_prompt_input(
    case: dict, request_text: str, questions: list[str], replies: list[dict], rules: list[dict],
    dept_names: list[str], example_response: str | None,
) -> str:
    materials = "\n\n".join(
        f"--- Materiał z {reply.get('department') or 'wydziału'}"
        f"{' (' + reply['filename'] + ')' if reply.get('filename') else ''} ---\n{reply['text']}"
        for reply in replies
    )
    question_list = "\n".join(f"{number}. {question}" for number, question in enumerate(questions, 1))
    rule_list = "\n".join(f"- {rule['source']} — {rule['title']}: {rule['content'][:PROMPT_RULE_CHARS]}" for rule in rules)
    return (
        f"SPRAWA: {case.get('case_number')}; data wpływu wniosku: {case.get('received_date') or ''}; "
        f"wnioskodawca: {case.get('applicant')}\n"
        f"PRZEDMIOT: {case.get('subject')}\n"
        f"KOMÓRKI MERYTORYCZNE: {', '.join(dept_names) or '(nie wskazano)'}\n"
        f"PYTANIA WNIOSKODAWCY:\n{question_list or '(brak wyodrębnionych pytań)'}\n\n"
        f'TREŚĆ WNIOSKU:\n"""\n{(request_text or "")[:PROMPT_REQUEST_CHARS]}\n"""\n\n'
        f'MATERIAŁY Z WYDZIAŁÓW:\n"""\n{materials[:PROMPT_TEXT_CHARS]}\n"""\n\n'
        f"PRZEPISY:\n{rule_list}\n\n"
        f'WZÓR Z ARCHIWUM (styl pisma UMB):\n"""\n{(example_response or "(brak)")[:PROMPT_EXAMPLE_CHARS]}\n"""'
    )


def draft_reply(
    case: dict,
    request_text: str,
    parsed: dict,
    replies: list[dict],
    rules: list[dict],
    categories: list[str],
    dept_names: list[str],
    example_response: str | None = None,
) -> tuple[str, list[dict], bool]:
    """Zwraca (treść projektu, fragmenty do anonimizacji wskazane przez model, czy użyto modelu)."""
    form = letters.addressee_form(case.get("applicant"), parsed.get("typ_wnioskodawcy"))
    questions = parsed.get("pytania") or []

    def with_model() -> tuple[str, list[dict], bool]:
        addressee = letters.ADDRESSEE[form]
        system = DRAFT_PROMPT.substitute(salutation=addressee["salutation"], by=addressee["by"], categories="; ".join(categories))
        user = _draft_prompt_input(case, request_text, questions, replies, rules, dept_names, example_response)
        data = llm.chat_json(system, user, max_tokens=config.LLM_DRAFT_MAX_TOKENS)
        text = str(data.get("draft_text") or "").strip()
        if not text:
            raise llm.LLMError("Model nie zwrócił treści projektu odpowiedzi.")
        candidates = [c for c in data.get("anonymization_candidates") or [] if isinstance(c, dict)]
        return text, candidates, True

    def without_model(failure: str | None) -> tuple[str, list[dict], bool]:
        text = letters.answer(case, form, questions, replies, dept_names)
        if failure:
            text = f"[UWAGA: model językowy niedostępny ({failure}) — projekt z szablonu UMB]\n{text}"
        return text, [], False

    return _with_fallback(with_model, without_model)
