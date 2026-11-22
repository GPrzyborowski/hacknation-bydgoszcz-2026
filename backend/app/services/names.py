"""Wykrywanie imion i nazwisk bez modelu językowego: popularne polskie imię i następujący po nim wyraz wielką literą.

Dopasowanie obejmuje odmianę („Jan Kowalski”, „Jana Kowalskiego”, „Annie Nowak”). Wynik to wyłącznie
podpowiedź do anonimizacji — osoby pełniące funkcje publiczne urzędnik odznacza.
"""
import re

from services.patterns import PL_LOWER, PL_UPPER, STREET_PREFIX

FIRST_NAMES = """
Adam Adrian Albert Aleksander Andrzej Antoni Arkadiusz Artur Bartłomiej Bartosz Bogdan Bogusław Bolesław Cezary
Czesław Damian Daniel Dariusz Dawid Dominik Edward Emil Eryk Filip Franciszek Gabriel Grzegorz Henryk Hubert Igor
Ireneusz Jacek Jakub Jan Janusz Jarosław Jerzy Józef Julian Kacper Kamil Karol Kazimierz Konrad Krystian Krzysztof
Leszek Łukasz Maciej Maksymilian Marcin Marek Marian Mariusz Mateusz Michał Mieczysław Mikołaj Miłosz Mirosław Norbert
Oskar Patryk Paweł Piotr Przemysław Radosław Rafał Robert Roman Ryszard Sebastian Sławomir Stanisław Stefan Szymon
Tadeusz Tomasz Wacław Waldemar Wiesław Wiktor Witold Władysław Włodzimierz Wojciech Zbigniew Zdzisław Zenon Zygmunt
Agata Agnieszka Aleksandra Alicja Amelia Aneta Aniela Anna Antonina Barbara Beata Bożena Danuta Dominika Dorota Edyta
Elżbieta Emilia Ewa Ewelina Gabriela Grażyna Halina Hanna Helena Irena Iwona Izabela Jadwiga Janina Joanna Jolanta
Julia Justyna Kamila Karolina Katarzyna Kinga Klaudia Krystyna Laura Lena Lidia Lucyna Magdalena Małgorzata Maria
Marianna Marta Marzena Monika Natalia Nikola Olga Oliwia Patrycja Paulina Renata Róża Sabina Stanisława Sylwia
Teresa Urszula Wanda Weronika Wiesława Wiktoria Zofia Zuzanna
""".split()

# Wyrazy, które po imieniu nie są nazwiskiem (np. „Jana Pawła II” zostaje — urzędnik je odznaczy).
_NOT_SURNAMES = {"Miasta", "Urzędu", "Wydziału", "Bydgoszczy", "Bydgoszcz", "Prezydenta", "Rady"}


def _inflected(name: str) -> str:
    """Wzorzec imienia w odmianie: Anna/Anny/Annie/Annę/Anną, Jan/Jana/Janowi/Janem, Marek/Marka (ruchome „e”)."""
    if name.endswith("a"):
        return re.escape(name[:-1]) + "(?:a|y|i|ie|ę|ą)"
    if name.endswith("ek"):
        return re.escape(name[:-2]) + "(?:ek|ka|kowi|kiem|ku)"
    return re.escape(name) + "(?:a|owi|em|ie|u)?"


_FIRST_NAME = "|".join(sorted((_inflected(name) for name in FIRST_NAMES), key=len, reverse=True))
_SURNAME = f"[{PL_UPPER}][{PL_LOWER}]+(?:-[{PL_UPPER}][{PL_LOWER}]+)?"
PERSON = re.compile(
    rf"\b(?:{_FIRST_NAME})\s+{_SURNAME}\b"
    rf"|\b[{PL_UPPER}]\.\s?[{PL_UPPER}][{PL_LOWER}]{{2,}}(?:-[{PL_UPPER}][{PL_LOWER}]+)?\b"  # „E. Góra”
)
_STREET_BEFORE = re.compile(rf"{STREET_PREFIX}\s*$")


def find_people(text: str) -> list[tuple[int, int]]:
    spans = []
    for match in PERSON.finditer(text):
        if match.group(0).split()[-1] in _NOT_SURNAMES:
            continue
        # „ul. Jana Pawła” to nazwa ulicy, nie osoba.
        if _STREET_BEFORE.search(text[max(0, match.start() - 6) : match.start()]):
            continue
        spans.append((match.start(), match.end()))
    return spans
