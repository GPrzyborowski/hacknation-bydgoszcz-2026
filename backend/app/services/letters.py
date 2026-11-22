"""Szablony pism odtworzone z pism BKS UMB z materiałów wyzwania:
- odpowiedź z materiałów wydziału ........ BKS.IV.1431.293.2025, .307.2025, .18.2026
- brak dysponenta informacji ............ BKS.IV.1431.15.2026, .17.2026
- kwerenda (przedłużenie terminu) ....... Kwerenda - BKS.IV.1431.543.2026
- wezwanie do doprecyzowania ............ Doprecyzowanie - BKS.IV.1431.509.2026
oraz pisma wewnętrzne do wydziałów (prośba o materiały, prośba o uszczegółowienie odpowiedzi).
Każde pismo to projekt — urzędnik je sprawdza, poprawia i sam wysyła.
"""
import re
from datetime import date

from config import OFFICE_NAME, OFFICE_NAME_GENITIVE
from services.deadlines import MONTHS_GENITIVE, format_short_iso, today

CLOSING = "Łączę wyrazy szacunku,"
DEPARTMENT_SALUTATION = "Szanowny Panie Dyrektorze / Szanowna Pani Dyrektor,"
DEPARTMENT_CLOSING = "Z poważaniem"
UDIP = "ustawy z dnia 6 września 2001 r. o dostępie do informacji publicznej"
PREVIOUS_ANSWER_EXCERPT = 400

ADDRESSEE = {
    "pan": {"salutation": "Szanowny Panie,", "by": "przez Pana"},
    "pani": {"salutation": "Szanowna Pani,", "by": "przez Panią"},
    "panstwo": {"salutation": "Szanowni Państwo,", "by": "przez Państwa"},
}

_ORGANIZATION_MARKERS = re.compile(
    r"\b(stowarzyszen\w*|fundacj\w*|s\.\s?a\.|sp\.\s?z\s?o\.\s?o\.|spółk\w*|parafi\w*|redakcj\w*|urząd|zarząd|"
    r"towarzystw\w*|związek|klub|instytut|kancelari\w*|firma|grupa|S\.A\.)",
    re.IGNORECASE,
)
_MALE_NAMES_ENDING_WITH_A = {"kuba", "barnaba", "bonawentura", "kosma", "jarema"}


def todo(note: str) -> str:
    return f"[DO UZUPEŁNIENIA: {note}]"


def addressee_form(applicant: str | None, applicant_type: str | None = None) -> str:
    """Pan / Pani / Państwo. Organizacja, adres e-mail albo sam inicjał to „Państwo”."""
    name = (applicant or "").strip()
    if (
        not name
        or "@" in name
        or _ORGANIZATION_MARKERS.search(name)
        or (applicant_type or "").lower().startswith(("organiz", "przedsi"))
    ):
        return "panstwo"
    first = name.split()[0].strip(".,")
    if len(first) <= 2 or len(name.split()) < 2:
        return "pan" if first.lower() in {"ksiądz", "ks"} else "panstwo"
    if first.lower().endswith("a") and first.lower() not in _MALE_NAMES_ENDING_WITH_A:
        return "pani"
    return "pan"


def date_words(day: date) -> str:
    """„25 września br.” w bieżącym roku, w innym — „25 września 2027 r.”."""
    year = "br." if day.year == today().year else f"{day.year} r."
    return f"{day.day} {MONTHS_GENITIVE[day.month - 1]} {year}"


def subject_phrase(subject: str | None) -> str:
    """Przedmiot wniosku w cudzysłowie: temat z rejestru jest w mianowniku, więc nie wstawiamy go
    bezpośrednio po „w zakresie” (urzędnik lub model może go przeredagować)."""
    text = (subject or "").strip().rstrip(".")
    return f"„{text[0].upper() + text[1:]}”" if text else todo("zakres wniosku")


def departments_phrase(names: list[str]) -> str:
    """„komórkę merytoryczną, tj. X Urzędu…” albo „komórki merytoryczne, tj. X, Y oraz Z Urzędu…”."""
    if len(names) > 1:
        return f"komórki merytoryczne, tj. {', '.join(names[:-1])} oraz {names[-1]} {OFFICE_NAME_GENITIVE}"
    return f"komórkę merytoryczną, tj. {names[0] if names else todo('nazwa wydziału')} {OFFICE_NAME_GENITIVE}"


def answer(case: dict, form: str, questions: list[str], replies: list[dict], dept_names: list[str]) -> str:
    """Projekt odpowiedzi bez modelu językowego: układ pisma UMB i materiały wydziałów do przeredagowania."""
    addressee = ADDRESSEE[form]
    parts = [
        addressee["salutation"],
        f"w odpowiedzi na wystosowany {addressee['by']} wniosek o udostępnienie informacji publicznej w zakresie "
        f"{subject_phrase(case.get('subject'))}, na podstawie materiału przygotowanego przez {departments_phrase(dept_names)} "
        "informuję, co następuje.",
    ]
    if len(questions) > 1:
        for number, question in enumerate(questions, 1):
            parts += [f"Ad {number}", f"[DO UZUPEŁNIENIA — odpowiedź na pytanie: {question}]"]
    else:
        parts.append("[DO UZUPEŁNIENIA — treść odpowiedzi na podstawie materiałów poniżej]")
    parts += [CLOSING, "", "--- Materiały przekazane przez komórki merytoryczne (usuń przed wysyłką) ---"]
    parts += [f"[{reply.get('department') or 'wydział'}] {reply['text'].strip()}" for reply in replies]
    return "\n".join(parts).strip()


def nie_dysponent(case: dict, form: str, entity: dict | None) -> str:
    addressee = ADDRESSEE[form]
    subject = subject_phrase(case.get("subject"))
    target = entity["name_genitive"] if entity else todo("podmiot właściwy (w dopełniaczu)")
    contact = entity["contact"] if entity else todo("dane kontaktowe podmiotu")
    return "\n".join(
        [
            addressee["salutation"],
            f"w odpowiedzi na wystosowany {addressee['by']} wniosek o udostępnienie informacji publicznej dotyczący {subject}, "
            f"uprzejmie informuję iż {OFFICE_NAME} nie jest dysponentem wnioskowanych danych.",
            f"Jednocześnie wskazuję, iż zgodnie z zasadą dostępu do informacji publicznej, wyrażoną w art. 4 ust. 3 {UDIP} "
            "(t.j. Dz. U. z 2022 r. poz. 902) obowiązane do udostępnienia informacji publicznej są podmioty publiczne "
            "będące w posiadaniu tych informacji.",
            f"W związku z powyższym {OFFICE_NAME} uprzejmie informuje, iż Wnioskodawca w zakresie informacji "
            f"dotyczących {subject} winien się zwrócić do {target} jako właściwego dysponenta danych.",
            "Poniżej zamieszczam dane do kontaktu:",
            contact,
            CLOSING,
        ]
    )


def kwerenda(case: dict, form: str, new_deadline: date) -> str:
    addressee = ADDRESSEE[form]
    return "\n".join(
        [
            addressee["salutation"],
            f"w odpowiedzi na wystosowany {addressee['by']} wniosek o udostępnienie informacji publicznej dotyczący "
            f"{subject_phrase(case.get('subject'))}, ze względu na konieczność przeprowadzenia całościowej kwerendy w zakresie "
            f"wnioskowanych danych powiadamiam, że ostateczna odpowiedź nastąpi w terminie późniejszym wskazanym w art. 13 "
            f"ust. 2 {UDIP} – orientacyjny termin udzielenia odpowiedzi: {date_words(new_deadline)}",
            CLOSING,
        ]
    )


def doprecyzowanie(case: dict, form: str, new_deadline: date, dept_names: list[str], details: str | None) -> str:
    addressee = ADDRESSEE[form]
    department = dept_names[0] if dept_names else todo("nazwa wydziału")
    scope = (details or "").strip() or todo("czego dotyczy doprecyzowanie")
    return "\n".join(
        [
            "WEZWANIE DO DOPRECYZOWANIA",
            "ZAKRESU OTRZYMANEGO WNIOSKU",
            addressee["salutation"],
            f"w związku z wystosowanym {addressee['by']} wnioskiem o udostępnienie informacji publicznej dotyczącym "
            f"{subject_phrase(case.get('subject'))}, komórka merytoryczna, tj. {department} {OFFICE_NAME_GENITIVE} "
            f"wnosi o doprecyzowanie wniosku: {scope}",
            "Proszę o przesłanie doprecyzowania w terminie 7 dni od otrzymania niniejszego pisma. Po upływie tego terminu "
            "wniosek zostanie pozostawiony bez rozpoznania, o czym Wnioskodawca zostanie powiadomiony odrębnym pismem.",
            "Jednocześnie stosownie do treści art. 13 ust. 2 ustawy z 06.09.2001 r. o dostępie do informacji publicznej "
            "(Dz. U. z 2022 r. poz. 902, z 2025 r. poz. 1844) powiadamiam, że wyznaczam nowy termin na rozpatrzenie wniosku, "
            f"wskazując dzień {date_words(new_deadline)}",
            CLOSING,
        ]
    )


def department_request(case: dict, dept: dict, questions: list[str], deadline_for_dept: str | None) -> str:
    """Prośba do wydziału o materiały do odpowiedzi."""
    question_list = "\n".join(f"{number}. {question}" for number, question in enumerate(questions, 1)) or f"— {case.get('subject')}"
    received = format_short_iso(case.get("received_date"), todo("data wniosku"))
    term = (
        f" w terminie do dnia {format_short_iso(deadline_for_dept, todo('data wniosku'))} r."
        if deadline_for_dept
        else " w możliwie najkrótszym terminie."
    )
    return (
        f"{DEPARTMENT_SALUTATION}\n\n"
        f"w związku z wnioskiem o udostępnienie informacji publicznej, który wpłynął do {OFFICE_NAME_GENITIVE} "
        f"w dniu {received} r. (znak sprawy: {case.get('case_number')}), "
        f"zwracam się z uprzejmą prośbą o przekazanie materiałów pozostających w zakresie działania komórki "
        f"({dept['code']} – {dept['name']}){term}\n\n"
        f"Przedmiot wniosku: {case.get('subject')}\n\nZakres pytań wnioskodawcy:\n{question_list}\n\n"
        "Jednocześnie proszę o wskazanie, czy przekazywane materiały zawierają dane osobowe lub informacje "
        "stanowiące tajemnicę przedsiębiorcy, a także czy którakolwiek z informacji jest już opublikowana w BIP.\n\n"
        f"{DEPARTMENT_CLOSING}"
    )


def clarification_request(case: dict, dept_name: str, details: str | None, previous_answer: str | None) -> str:
    """Prośba do wydziału o uszczegółowienie przekazanej odpowiedzi."""
    received = format_short_iso(case.get("received_date"), todo("data wniosku"))
    deadline = format_short_iso(case.get("deadline_date"), todo("termin odpowiedzi"))
    parts = [
        DEPARTMENT_SALUTATION,
        f"w nawiązaniu do przekazanych materiałów w sprawie wniosku o udostępnienie informacji publicznej "
        f"z dnia {received} r. (znak sprawy: {case.get('case_number')}), dotyczącego: {case.get('subject')}, "
        f"uprzejmie proszę o uszczegółowienie odpowiedzi przekazanej przez {dept_name} w zakresie:",
        (details or "").strip() or todo("czego brakuje w odpowiedzi"),
    ]
    if previous_answer:
        excerpt = previous_answer.strip()[:PREVIOUS_ANSWER_EXCERPT]
        ellipsis = "…" if len(previous_answer) > PREVIOUS_ANSWER_EXCERPT else ""
        parts.append(f"Dotychczas przekazano: „{excerpt}{ellipsis}”")
    parts += [
        f"Termin udzielenia odpowiedzi wnioskodawcy upływa {deadline} r., dlatego proszę o przekazanie uzupełnienia "
        "w możliwie najkrótszym terminie, a w razie braku takiej możliwości — o informację o przewidywanym terminie "
        "(§ 11 ust. 5 Zarządzenia nr 535/2024).",
        DEPARTMENT_CLOSING,
    ]
    return "\n\n".join(parts)
