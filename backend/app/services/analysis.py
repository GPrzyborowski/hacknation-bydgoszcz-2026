"""Zadania LLM: przetworzenie wniosku, projekt odpowiedzi, prośba do wydziału — z heurystycznym zapasem."""
import json
import re
from datetime import date

import config
from services import letters, llm
from services.deadlines import parse_date

MAX_PROMPT_CHARS = 12000

PARSED_KEYS = [
    "wnioskodawca", "typ_wnioskodawcy", "adres_do_odpowiedzi", "forma_odpowiedzi", "data_na_pismie",
    "temat_skrot", "pytania", "kategoria", "czy_to_wniosek_udip", "uwagi",
]

CATEGORIES = [
    "inwestycje", "finanse i budżet", "zamówienia publiczne", "nieruchomości", "budownictwo", "edukacja",
    "sport", "kultura", "środowisko", "gospodarka odpadami", "transport i drogi", "zatrudnienie i kadry",
    "rada miasta", "promocja", "zdrowie i pomoc społeczna", "podatki i opłaty", "organizacja urzędu", "inne",
]

APPLICANT_TYPES = ["osoba fizyczna", "organizacja", "dziennikarz", "przedsiębiorca", "radny", "inny"]


# --- 1. Przetworzenie wniosku -----------------------------------------------------------------

PARSE_SYSTEM = """Jesteś asystentem urzędnika Urzędu Miasta Bydgoszczy obsługującego wnioski o udostępnienie informacji publicznej (u.d.i.p.).
Z treści wniosku wyodrębnij dane i zwróć WYŁĄCZNIE obiekt JSON o kluczach:
- "wnioskodawca": imię i nazwisko lub nazwa wnioskodawcy albo null,
- "typ_wnioskodawcy": jedno z: {types} albo null,
- "adres_do_odpowiedzi": e-mail lub adres korespondencyjny albo null,
- "forma_odpowiedzi": "email", "e-Doręczenia", "poczta", "odbiór osobisty", "ePUAP" albo "nieokreślona",
- "data_na_pismie": data pisma w formacie RRRR-MM-DD albo null,
- "temat_skrot": zwięzłe streszczenie przedmiotu wniosku (do 12 słów),
- "pytania": lista wszystkich pytań/żądań wnioskodawcy, każde jako osobny string, bez parafrazowania sensu,
- "kategoria": jedno z: {categories},
- "czy_to_wniosek_udip": true jeśli to wniosek o informację publiczną, false jeśli np. skarga, petycja, wniosek w trybie KPA,
- "uwagi": krótkie uwagi analityczne: czy to informacja przetworzona (art. 3 ust. 1 pkt 1), braki formalne, czy dotyczy danych osobowych, czy UMB może nie być dysponentem,
- "sugerowane_wydzialy": lista maks. 3 obiektów {{"code": symbol z listy, "reason": krótkie uzasadnienie}}.
Lista komórek UMB (symbol – nazwa – zakres):
{departments}
Nie wymyślaj danych, których nie ma we wniosku — wtedy wpisz null."""


def parse_request(text: str, departments: list[dict]) -> tuple[dict, list[dict], bool]:
    """Zwraca (parsed_request, sugestie_wydziałów_LLM, czy_użyto_LLM). LLMError/LLMForbidden przechodzą wyżej."""
    try:
        system = PARSE_SYSTEM.format(
            types=", ".join(APPLICANT_TYPES),
            categories=", ".join(CATEGORIES),
            departments="\n".join(f"{d['code']} – {d['name']} – {d['keywords']}" for d in departments),
        )
        data = llm.chat_json(system, f"TREŚĆ WNIOSKU:\n\"\"\"\n{text[:MAX_PROMPT_CHARS]}\n\"\"\"")
        return _normalize_parsed(data, text), list(data.get("sugerowane_wydzialy") or []), True
    except llm.LLMDisabled:
        return heuristic_parse(text), [], False
    except llm.LLMError as exc:
        if not config.LLM_FALLBACK_HEURISTIC:
            raise
        parsed = heuristic_parse(text)
        parsed["uwagi"] = f"Model językowy niedostępny ({exc}) — użyto analizy heurystycznej. " + parsed["uwagi"]
        return parsed, [], False


def _normalize_parsed(data: dict, text: str) -> dict:
    fallback = heuristic_parse(text)
    out = {}
    for key in PARSED_KEYS:
        value = data.get(key)
        if value in ("", "null", "brak"):
            value = None
        out[key] = value
    pytania = out["pytania"]
    if isinstance(pytania, str):
        pytania = [pytania]
    out["pytania"] = [str(p).strip() for p in (pytania or []) if str(p).strip()] or fallback["pytania"]
    out["temat_skrot"] = str(out["temat_skrot"] or fallback["temat_skrot"])
    out["kategoria"] = str(out["kategoria"] or fallback["kategoria"])
    out["uwagi"] = str(out["uwagi"] or "")
    v = out["czy_to_wniosek_udip"]
    out["czy_to_wniosek_udip"] = v if isinstance(v, bool) else str(v).lower() in {"true", "tak", "1"}
    if out["data_na_pismie"]:
        parsed, _ = parse_date(out["data_na_pismie"])
        out["data_na_pismie"] = parsed.isoformat() if parsed else None
    for key in ("wnioskodawca", "typ_wnioskodawcy", "adres_do_odpowiedzi", "forma_odpowiedzi"):
        out[key] = str(out[key]).strip() if out[key] is not None else fallback[key]
    return out


EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
ADDRESS_RE = re.compile(r"(?:ul\.|al\.|os\.|pl\.)\s*[^\n,]{2,40}\d+[a-zA-Z]?(?:/\d+)?(?:,?\s*\d{2}-\d{3}\s+\w+)?", re.IGNORECASE)


_UP = "A-ZŁŚŻŹĆŃÓĘĄ"
_LO = "a-ząćęłńóśźż"
_PERSON = re.compile(rf"(?:[{_UP}][{_LO}]+|[{_UP}]\.)(?:[ -][{_UP}][{_LO}]+){{1,2}}")
_ORG = re.compile(
    rf"((?:Stowarzyszenie|Fundacja|Parafia|Redakcja|Proboszcz Parafii|Spółdzielnia|Towarzystwo)\s[^,\n]{{3,80}}"
    rf"|[{_UP}][\w-]+(?:\s[{_UP}][\w-]+)*\s(?:S\.A\.|sp\. z o\.o\.|Sp\. z o\.o\.))"
)
_CLOSINGS = re.compile(r"^(?:--\s*)?(?:pozdrawiam|z poważaniem|z wyrazami szacunku|łączę wyrazy szacunku|z wyrazami)\b[\s|,]*", re.IGNORECASE)


def _heuristic_applicant(text: str, lines: list[str]) -> str | None:
    """Wnioskodawca wg wzorców z wniosków testowych UMB: pole „Wnioskodawca:”, podpis po formule
    grzecznościowej („Pozdrawiam | Ewa Góra”, „E. Góra”), nazwa organizacji na końcu lub w pierwszym zdaniu."""
    m = re.search(r"(?:wnioskodawca|imię i nazwisko)\s*[:\-]\s*(.+)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()[:120]
    tail = [l for l in lines[-8:] if l.strip("- ")]
    for i, line in enumerate(tail):
        if _CLOSINGS.match(line):
            rest = _CLOSINGS.sub("", line).strip(" |")
            candidates = [rest] if rest else tail[i + 1 : i + 3]
            for cand in candidates:
                org = _ORG.search(cand)
                if org:
                    return org.group(1).strip()
                if _PERSON.fullmatch(cand.strip()):
                    return cand.strip()
    for line in reversed(tail):
        org = _ORG.search(line) if len(line) < 70 else None  # krótkie wiersze = podpis, nie treść
        if org:
            return org.group(1).strip()
        if _PERSON.fullmatch(line.strip()):
            return line.strip()
    # Organizacja przedstawiająca się w pierwszym zdaniu („Stowarzyszenie …, organizacja pożytku publicznego…”).
    for line in lines[:6]:
        org = _ORG.match(line)
        if org:
            return org.group(1).strip().rstrip(",")
    # Wniosek mailowy bez podpisu — rejestr UMB wpisuje wtedy adres e-mail (sprawa BKS.IV.1431.17.2026).
    email = EMAIL_RE.search(text)
    return email.group(0) if email else None


def heuristic_parse(text: str) -> dict:
    """Ekstrakcja regułowa — działa bez modelu językowego (tryb developerski / awaryjny)."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    lowered = text.lower()

    email = EMAIL_RE.search(text)
    address = ADDRESS_RE.search(text)
    applicant = _heuristic_applicant(text, lines)

    data_pisma = None
    for line in lines[:12]:
        if re.search(r"\b(dnia|dn\.|\d{1,2}[./-]\d{1,2}[./-]\d{4}|\d{4}-\d{2}-\d{2})", line):
            parsed, _ = parse_date(line)
            if parsed:
                data_pisma = parsed.isoformat()
                break

    questions: list[str] = []
    for line in lines:
        if line.endswith("?") or re.match(r"^(\d+[.)]|[a-z][.)]|[-•–])\s+\S", line):
            q = re.sub(r"^(\d+[.)]|[a-z][.)]|[-•–])\s+", "", line)
            if len(q) > 8:
                questions.append(q)
    if not questions:
        m = re.search(r"(?:proszę o|wnoszę o|wnioskuję o|zwracam się z (?:uprzejmą )?prośbą o)\s+(.{10,400}?)(?:\.|$)", text, re.IGNORECASE | re.DOTALL)
        if m:
            questions.append(" ".join(m.group(1).split()))

    subject_line = next(
        # „Temat:” z nagłówka e-maila bywa pusty (wniosek BKS.IV.1431.543.2026) — wymagamy treści po prefiksie.
        (l for l in lines if re.match(r"^(dotyczy|dot\.|w sprawie|temat)\b\s*:?\s*\S.{8,}", l, re.IGNORECASE)), None
    )
    scope = re.search(
        r"informacji publicznej\s+(?:w zakresie|na temat|dotycząc\w*|dot\.)\s+(.{10,200}?)(?:[.:;]|\s+z następujących|$)",
        " ".join(lines), re.IGNORECASE,
    )
    meaningful = [l for l in lines if len(l) > 25 and not re.match(r"^(dzień dobry|witam|szanown|biuro|urząd)", l, re.IGNORECASE)]
    if subject_line:
        subject = re.sub(r"^(dotyczy|dot\.|w sprawie|temat)\s*:?\s*", "", subject_line, flags=re.IGNORECASE)
    elif scope:
        subject = scope.group(1)
    elif questions:
        subject = questions[0]
    else:
        subject = meaningful[0] if meaningful else (lines[0] if lines else "")

    if "e-doręcze" in lowered or "e-dorecze" in lowered:
        forma = "e-Doręczenia"
    elif "e-mail" in lowered or "mail" in lowered or "elektroniczn" in lowered:
        forma = "email"
    elif "poczt" in lowered or "listown" in lowered:
        forma = "poczta"
    elif "epuap" in lowered:
        forma = "ePUAP"
    else:
        forma = "nieokreślona"

    if "redakc" in lowered or "dziennikar" in lowered or "gazet" in lowered or "portal" in lowered:
        typ = "dziennikarz"
    elif applicant and _ORG.search(applicant):
        typ = "organizacja"
    elif re.search(r"\b(fundacja|stowarzyszenie|spółdzielnia|parafia)\b", lowered[:300]):
        typ = "organizacja"
    elif applicant:
        typ = "osoba fizyczna"
    else:
        typ = None

    kategoria = "inne"
    for cat, kws in {
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
    }.items():
        if any(re.search(r"\b" + re.escape(k), lowered) for k in kws):
            kategoria = cat
            break

    uwagi = []
    if "informacji publicznej" not in lowered and "u.d.i.p" not in lowered and "dostępie do informacji" not in lowered:
        uwagi.append("Brak wprost powołania się na u.d.i.p. — zweryfikuj tryb.")
    if re.search(r"zestawieni|analiz|wylicz|porównani|sumaryczn", lowered):
        uwagi.append("Możliwa informacja przetworzona (art. 3 ust. 1 pkt 1 u.d.i.p.).")
    if not (email or address):
        uwagi.append("Brak adresu do odpowiedzi.")
    uwagi.append("Analiza heurystyczna (bez modelu językowego) — sprawdź dane.")

    return {
        "wnioskodawca": applicant,
        "typ_wnioskodawcy": typ,
        "adres_do_odpowiedzi": email.group(0) if email else (address.group(0).strip() if address else None),
        "forma_odpowiedzi": forma,
        "data_na_pismie": data_pisma,
        "temat_skrot": (subject or "")[:160],
        "pytania": questions[:15],
        "kategoria": kategoria,
        "czy_to_wniosek_udip": "informac" in lowered and "publiczn" in lowered,
        "uwagi": " ".join(uwagi),
    }


# --- 2. Projekt odpowiedzi -------------------------------------------------------------------

DRAFT_SYSTEM = """Jesteś asystentem urzędnika Biura Komunikacji Społecznej Urzędu Miasta Bydgoszczy. Przygotuj PROJEKT pisma — odpowiedzi na wniosek o udostępnienie informacji publicznej — w stylu pism BKS UMB.
Układ pisma (bez nagłówka urzędu, daty, znaku sprawy i podpisu — te dodaje system):
1. Zwrot: "{salutation}"
2. Akapit otwierający, np.: "w odpowiedzi na wystosowany {by} wniosek o udostępnienie informacji publicznej w zakresie <zakres>, na podstawie materiału przygotowanego przez komórkę merytoryczną, tj. <nazwa wydziału> Urzędu Miasta Bydgoszczy informuję, co następuje."
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
Kategorie anonimizacji (wg listy UMB): {categories}"""


def draft_reply(
    case: dict,
    request_text: str,
    parsed: dict | None,
    replies: list[dict],
    rules: list[dict],
    categories: list[str],
    dept_names: list[str] | None = None,
    example_response: str | None = None,
) -> tuple[str, list[dict], bool]:
    dept_names = dept_names or []
    form = letters.addressee_form(case.get("applicant"), (parsed or {}).get("typ_wnioskodawcy"))
    addressee = letters.ADDRESSEE[form]
    received = case.get("received_date") or ""
    materials = "\n\n".join(
        f"--- Materiał z {r.get('department') or 'wydziału'}{' (' + r['filename'] + ')' if r.get('filename') else ''} ---\n{r['text']}"
        for r in replies
    )
    questions = (parsed or {}).get("pytania") or []
    rules_text = "\n".join(f"- {r['source']} — {r['title']}: {r['content'][:600]}" for r in rules)
    user = (
        f"SPRAWA: {case.get('case_number')}; data wpływu wniosku: {received}; wnioskodawca: {case.get('applicant')}\n"
        f"PRZEDMIOT: {case.get('subject')}\n"
        f"KOMÓRKI MERYTORYCZNE: {', '.join(dept_names) or '(nie wskazano)'}\n"
        f"PYTANIA WNIOSKODAWCY:\n" + ("\n".join(f"{i + 1}. {q}" for i, q in enumerate(questions)) or "(brak wyodrębnionych pytań)") + "\n\n"
        f"TREŚĆ WNIOSKU:\n\"\"\"\n{(request_text or '')[:4000]}\n\"\"\"\n\n"
        f"MATERIAŁY Z WYDZIAŁÓW:\n\"\"\"\n{materials[:MAX_PROMPT_CHARS]}\n\"\"\"\n\n"
        f"PRZEPISY:\n{rules_text}\n\n"
        f"WZÓR Z ARCHIWUM (styl pisma UMB):\n\"\"\"\n{(example_response or '(brak)')[:2500]}\n\"\"\""
    )
    system = (
        DRAFT_SYSTEM.replace("{salutation}", addressee["salutation"])
        .replace("{by}", addressee["by"])
        .replace("{categories}", "; ".join(categories))
    )
    try:
        data = llm.chat_json(system, user, max_tokens=8192)
        text = str(data.get("draft_text") or "").strip()
        if not text:
            raise llm.LLMError("Model nie zwrócił treści projektu odpowiedzi.")
        cands = [c for c in (data.get("anonymization_candidates") or []) if isinstance(c, dict)]
        return text, cands, True
    except llm.LLMDisabled:
        return letters.answer(case, form, questions, replies, dept_names), [], False
    except llm.LLMError as exc:
        if not config.LLM_FALLBACK_HEURISTIC:
            raise
        note = f"[UWAGA: model językowy niedostępny ({exc}) — projekt z szablonu UMB]\n"
        return note + letters.answer(case, form, questions, replies, dept_names), [], False


def _pl_date(iso_value: str | None) -> str:
    try:
        d = date.fromisoformat(iso_value or "")
        return d.strftime("%d.%m.%Y")
    except ValueError:
        return "[DO UZUPEŁNIENIA: data wniosku]"


# --- 3. Prośba do wydziału -------------------------------------------------------------------

def department_request_template(case: dict, dept: dict, questions: list[str], deadline_for_dept: str | None) -> str:
    """Szablon pisma wewnętrznego — deterministyczny, urzędnik edytuje i wysyła sam."""
    q_text = "\n".join(f"{i}. {q}" for i, q in enumerate(questions, 1)) or f"— {case.get('subject')}"
    term = f" w terminie do dnia {_pl_date(deadline_for_dept)} r." if deadline_for_dept else " w możliwie najkrótszym terminie."
    return (
        f"Szanowny Panie Dyrektorze / Szanowna Pani Dyrektor,\n\n"
        f"w związku z wnioskiem o udostępnienie informacji publicznej, który wpłynął do Urzędu Miasta Bydgoszczy "
        f"w dniu {_pl_date(case.get('received_date'))} r. (znak sprawy: {case.get('case_number')}), "
        f"zwracam się z uprzejmą prośbą o przekazanie materiałów pozostających w zakresie działania komórki ({dept['code']} – {dept['name']}){term}\n\n"
        f"Przedmiot wniosku: {case.get('subject')}\n\nZakres pytań wnioskodawcy:\n{q_text}\n\n"
        "Jednocześnie proszę o wskazanie, czy przekazywane materiały zawierają dane osobowe lub informacje "
        "stanowiące tajemnicę przedsiębiorcy, a także czy którakolwiek z informacji jest już opublikowana w BIP.\n\n"
        "Z poważaniem"
    )


def dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False)
