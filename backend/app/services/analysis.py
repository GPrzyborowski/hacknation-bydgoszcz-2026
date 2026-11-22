"""Zadania modelu Gemini: przetworzenie wniosku i projekt odpowiedzi na podstawie materiałów wydziałów."""
from string import Template

import config
from schemas import ParsedRequest
from services import letters, llm
from services.deadlines import parse_date

PROMPT_TEXT_CHARS = 12000
PROMPT_REQUEST_CHARS = 4000
PROMPT_RULE_CHARS = 600
PROMPT_EXAMPLE_CHARS = 2500

CATEGORIES = [
    "inwestycje", "finanse i budżet", "zamówienia publiczne", "nieruchomości", "budownictwo", "edukacja",
    "sport", "kultura", "środowisko", "gospodarka odpadami", "transport i drogi", "zatrudnienie i kadry",
    "rada miasta", "promocja", "zdrowie i pomoc społeczna", "podatki i opłaty", "organizacja urzędu", "inne",
]
APPLICANT_TYPES = ["osoba fizyczna", "organizacja", "dziennikarz", "przedsiębiorca", "radny", "inny"]


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


def parse_request(text: str, departments: list[dict]) -> tuple[dict, list[dict]]:
    """Zwraca (przetworzone zgłoszenie, wydziały wskazane przez model)."""
    system = PARSE_PROMPT.substitute(
        types=", ".join(APPLICANT_TYPES),
        categories=", ".join(CATEGORIES),
        departments="\n".join(f"{d['code']} – {d['name']} – {d['keywords']}" for d in departments),
    )
    data = llm.chat_json(system, f'TREŚĆ WNIOSKU:\n"""\n{text[:PROMPT_TEXT_CHARS]}\n"""')
    return _normalize_parsed(data), list(data.get("sugerowane_wydzialy") or [])


def _normalize_parsed(data: dict) -> dict:
    """Odpowiedź modelu w kształcie ParsedRequest: brakujące pola puste, typy ujednolicone."""
    parsed = {key: (None if data.get(key) in ("", "null", "brak") else data.get(key)) for key in ParsedRequest.model_fields}

    questions = parsed["pytania"]
    if isinstance(questions, str):
        questions = [questions]
    parsed["pytania"] = [str(q).strip() for q in questions or [] if str(q).strip()]
    parsed["temat_skrot"] = str(parsed["temat_skrot"] or "")
    parsed["kategoria"] = str(parsed["kategoria"] or "inne")
    parsed["uwagi"] = str(parsed["uwagi"] or "")
    is_udip = parsed["czy_to_wniosek_udip"]
    parsed["czy_to_wniosek_udip"] = is_udip if isinstance(is_udip, bool) else str(is_udip).lower() in {"true", "tak", "1"}
    if parsed["data_na_pismie"]:
        letter_date, _ = parse_date(parsed["data_na_pismie"])
        parsed["data_na_pismie"] = letter_date.isoformat() if letter_date else None
    for key in ("wnioskodawca", "typ_wnioskodawcy", "adres_do_odpowiedzi", "forma_odpowiedzi"):
        parsed[key] = str(parsed[key]).strip() if parsed[key] is not None else None
    return parsed


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
) -> tuple[str, list[dict]]:
    """Zwraca (treść projektu, fragmenty do anonimizacji wskazane przez model)."""
    form = letters.addressee_form(case.get("applicant"), parsed.get("typ_wnioskodawcy"))
    questions = parsed.get("pytania") or []
    addressee = letters.ADDRESSEE[form]
    system = DRAFT_PROMPT.substitute(salutation=addressee["salutation"], by=addressee["by"], categories="; ".join(categories))
    user = _draft_prompt_input(case, request_text, questions, replies, rules, dept_names, example_response)
    data = llm.chat_json(system, user, max_tokens=config.LLM_DRAFT_MAX_TOKENS)
    text = str(data.get("draft_text") or "").strip()
    if not text:
        raise llm.LLMError("Model nie zwrócił treści projektu odpowiedzi.")
    candidates = [c for c in data.get("anonymization_candidates") or [] if isinstance(c, dict)]
    return text, candidates

