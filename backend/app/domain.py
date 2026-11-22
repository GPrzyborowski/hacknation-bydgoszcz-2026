"""Słownik domeny: statusy spraw, rodzaje pism, statusy odpowiedzi wydziałów.

Wartości są częścią kontraktu API i zapisu w bazie (StrEnum zapisuje się w SQLite jako zwykły tekst).
"""
from enum import StrEnum


class CaseStatus(StrEnum):
    brak_dzialan = "brak_dzialan"
    zapytania_wyslane = "zapytania_wyslane"
    kwerenda = "kwerenda"
    doprecyzowanie = "doprecyzowanie"
    odpowiedz_w_przygotowaniu = "odpowiedz_w_przygotowaniu"
    przygotowana_odpowiedz = "przygotowana_odpowiedz"
    odpowiedz_wyslana = "odpowiedz_wyslana"


class ProcedureMode(StrEnum):
    zwykla = "zwykla"
    bip = "bip"
    przetworzona = "przetworzona"
    odmowa = "odmowa"
    nie_dysponent = "nie_dysponent"


class LetterKind(StrEnum):
    odpowiedz = "odpowiedz"
    nie_dysponent = "nie_dysponent"
    kwerenda = "kwerenda"
    doprecyzowanie = "doprecyzowanie"


class DocumentKind(StrEnum):
    wniosek = "wniosek"
    odpowiedz = "odpowiedz"
    nie_dysponent = "nie_dysponent"
    kwerenda = "kwerenda"
    doprecyzowanie = "doprecyzowanie"


class DeptStatus(StrEnum):
    oczekuje = "oczekuje"
    odpowiedzial = "odpowiedzial"
    uszczegolowienie = "uszczegolowienie"


class Urgency(StrEnum):
    overdue = "overdue"
    today = "today"
    tomorrow = "tomorrow"
    soon = "soon"
    normal = "normal"
    done = "done"


DEPT_STATUS_LABELS = {
    DeptStatus.oczekuje: "czeka na odpowiedź",
    DeptStatus.odpowiedzial: "odpowiedział",
    DeptStatus.uszczegolowienie: "poproszono o uszczegółowienie",
}

# Kwerenda i wezwanie do doprecyzowania to pisma w toku sprawy: przedłużają ją, ale jej nie zamykają.
INTERIM_LETTERS = frozenset({LetterKind.kwerenda, LetterKind.doprecyzowanie})

LETTER_STATUS = {
    LetterKind.kwerenda: CaseStatus.kwerenda,
    LetterKind.doprecyzowanie: CaseStatus.doprecyzowanie,
    LetterKind.nie_dysponent: CaseStatus.odpowiedz_w_przygotowaniu,
    LetterKind.odpowiedz: CaseStatus.odpowiedz_w_przygotowaniu,
}


def initial_status(departments: list[str]) -> CaseStatus:
    """Nowa sprawa z przypisanymi wydziałami czeka na ich odpowiedzi, bez wydziałów — na działania urzędnika."""
    return CaseStatus.zapytania_wyslane if departments else CaseStatus.brak_dzialan
