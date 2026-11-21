"""Szablony pism BKS UMB odtworzone z materiałów wyzwania:
- odpowiedź z materiałów wydziału ........ BKS.IV.1431.293.2025, .307.2025, .18.2026
- brak dysponenta informacji ............ BKS.IV.1431.15.2026, .17.2026
- kwerenda (przedłużenie terminu) ....... Kwerenda - BKS.IV.1431.543.2026
- wezwanie do doprecyzowania ............ Doprecyzowanie - BKS.IV.1431.509.2026
Tekst pisma to zawsze projekt — urzędnik go sprawdza, poprawia i sam wysyła.
"""
import re
from datetime import date

from services.deadlines import MONTHS_GENITIVE, today

CLOSING = "Łączę wyrazy szacunku,"
TODO = "[DO UZUPEŁNIENIA{}]"

_ORG_MARKERS = re.compile(
    r"\b(stowarzyszen\w*|fundacj\w*|s\.\s?a\.|sp\.\s?z\s?o\.\s?o\.|spółk\w*|parafi\w*|redakcj\w*|urząd|zarząd|"
    r"towarzystw\w*|związek|klub|instytut|kancelari\w*|firma|grupa|S\.A\.)",
    re.IGNORECASE,
)
_MALE_A_NAMES = {"kuba", "barnaba", "bonawentura", "kosma", "jarema"}

ADDRESSEE = {
    "pan": {"salutation": "Szanowny Panie,", "by": "przez Pana"},
    "pani": {"salutation": "Szanowna Pani,", "by": "przez Panią"},
    "panstwo": {"salutation": "Szanowni Państwo,", "by": "przez Państwa"},
}


def addressee_form(applicant: str | None, applicant_type: str | None = None) -> str:
    """Pan / Pani / Państwo — na podstawie wnioskodawcy (organizacja, e-mail lub inicjał → Państwo)."""
    name = (applicant or "").strip()
    if not name or "@" in name or _ORG_MARKERS.search(name) or (applicant_type or "").lower().startswith(("organiz", "przedsi")):
        return "panstwo"
    first = name.split()[0].strip(".,")
    if len(first) <= 2 or len(name.split()) < 2:
        return "pan" if first.lower() in {"ksiądz", "ks"} else "panstwo"
    if first.lower().endswith("a") and first.lower() not in _MALE_A_NAMES:
        return "pani"
    return "pan"


def date_words(d: date) -> str:
    """„25 września br.” (bieżący rok) albo „25 września 2027 r.” — jak w pismach UMB."""
    suffix = "br." if d.year == today().year else f"{d.year} r."
    return f"{d.day} {MONTHS_GENITIVE[d.month - 1]} {suffix}"


def subject_phrase(subject: str | None) -> str:
    """Przedmiot wniosku w cudzysłowie — temat z rejestru jest w mianowniku, więc nie wstawiamy go
    bezpośrednio po „w zakresie” (urzędnik lub model może przeredagować na dopełniacz)."""
    s = (subject or "").strip().rstrip(".")
    if not s:
        return TODO.format(": zakres wniosku")
    return f"„{s[0].upper() + s[1:]}”"


def departments_phrase(names: list[str]) -> str:
    if not names:
        return "komórkę merytoryczną, tj. " + TODO.format(": nazwa wydziału") + " Urzędu Miasta Bydgoszczy"
    if len(names) == 1:
        return f"komórkę merytoryczną, tj. {names[0]} Urzędu Miasta Bydgoszczy"
    return "komórki merytoryczne, tj. " + ", ".join(names[:-1]) + f" oraz {names[-1]} Urzędu Miasta Bydgoszczy"


def answer(case: dict, form: str, questions: list[str], replies: list[dict], dept_names: list[str]) -> str:
    """Projekt odpowiedzi bez modelu językowego: układ pisma UMB + materiały wydziałów do przeredagowania."""
    a = ADDRESSEE[form]
    parts = [
        a["salutation"],
        f"w odpowiedzi na wystosowany {a['by']} wniosek o udostępnienie informacji publicznej w zakresie "
        f"{subject_phrase(case.get('subject'))}, na podstawie materiału przygotowanego przez {departments_phrase(dept_names)} "
        "informuję, co następuje.",
    ]
    if len(questions) > 1:
        for i, q in enumerate(questions, 1):
            parts += [f"Ad {i}", TODO.format(f" — odpowiedź na pytanie: {q}")]
    else:
        parts.append(TODO.format(" — treść odpowiedzi na podstawie materiałów poniżej"))
    parts.append(CLOSING)
    parts.append("")
    parts.append("--- Materiały przekazane przez komórki merytoryczne (usuń przed wysyłką) ---")
    for r in replies:
        parts.append(f"[{r.get('department') or 'wydział'}] {r['text'].strip()}")
    return "\n".join(parts).strip()


def nie_dysponent(case: dict, form: str, entity: dict | None) -> str:
    a = ADDRESSEE[form]
    subject = subject_phrase(case.get("subject"))
    target = entity["name_genitive"] if entity else TODO.format(": podmiot właściwy (w dopełniaczu)")
    contact = entity["contact"] if entity else TODO.format(": dane kontaktowe podmiotu")
    return "\n".join(
        [
            a["salutation"],
            f"w odpowiedzi na wystosowany {a['by']} wniosek o udostępnienie informacji publicznej dotyczący {subject}, "
            "uprzejmie informuję iż Urząd Miasta Bydgoszczy nie jest dysponentem wnioskowanych danych.",
            "Jednocześnie wskazuję, iż zgodnie z zasadą dostępu do informacji publicznej, wyrażoną w art. 4 ust. 3 ustawy "
            "z dnia 6 września 2001 r. o dostępie do informacji publicznej (t.j. Dz. U. z 2022 r. poz. 902) obowiązane do "
            "udostępnienia informacji publicznej są podmioty publiczne będące w posiadaniu tych informacji.",
            f"W związku z powyższym Urząd Miasta Bydgoszczy uprzejmie informuje, iż Wnioskodawca w zakresie informacji "
            f"dotyczących {subject} winien się zwrócić do {target} jako właściwego dysponenta danych.",
            "Poniżej zamieszczam dane do kontaktu:",
            contact,
            CLOSING,
        ]
    )


def kwerenda(case: dict, form: str, new_deadline: date) -> str:
    a = ADDRESSEE[form]
    return "\n".join(
        [
            a["salutation"],
            f"w odpowiedzi na wystosowany {a['by']} wniosek o udostępnienie informacji publicznej dotyczący "
            f"{subject_phrase(case.get('subject'))}, ze względu na konieczność przeprowadzenia całościowej kwerendy w zakresie "
            "wnioskowanych danych powiadamiam, że ostateczna odpowiedź nastąpi w terminie późniejszym wskazanym w art. 13 "
            "ust. 2 ustawy z dnia 6 września 2001 r. o dostępie do informacji publicznej – orientacyjny termin udzielenia "
            f"odpowiedzi: {date_words(new_deadline)}",
            CLOSING,
        ]
    )


def doprecyzowanie(case: dict, form: str, new_deadline: date, dept_names: list[str], details: str | None) -> str:
    a = ADDRESSEE[form]
    by_inst = {"pan": "przez Pana", "pani": "przez Panią", "panstwo": "przez Państwa"}[form]
    dept = f"komórka merytoryczna, tj. {dept_names[0]} Urzędu Miasta Bydgoszczy" if dept_names else (
        "komórka merytoryczna, tj. " + TODO.format(": nazwa wydziału") + " Urzędu Miasta Bydgoszczy"
    )
    scope = (details or "").strip() or TODO.format(": czego dotyczy doprecyzowanie")
    return "\n".join(
        [
            "WEZWANIE DO DOPRECYZOWANIA",
            "ZAKRESU OTRZYMANEGO WNIOSKU",
            a["salutation"],
            f"w związku z wystosowanym {by_inst} wnioskiem o udostępnienie informacji publicznej dotyczącym "
            f"{subject_phrase(case.get('subject'))}, {dept} wnosi o doprecyzowanie wniosku: {scope}",
            "Proszę o przesłanie doprecyzowania w terminie 7 dni od otrzymania niniejszego pisma. Po upływie tego terminu "
            "wniosek zostanie pozostawiony bez rozpoznania, o czym Wnioskodawca zostanie powiadomiony odrębnym pismem.",
            "Jednocześnie stosownie do treści art. 13 ust. 2 ustawy z 06.09.2001 r. o dostępie do informacji publicznej "
            "(Dz. U. z 2022 r. poz. 902, z 2025 r. poz. 1844) powiadamiam, że wyznaczam nowy termin na rozpatrzenie wniosku, "
            f"wskazując dzień {date_words(new_deadline)}",
            CLOSING,
        ]
    )
