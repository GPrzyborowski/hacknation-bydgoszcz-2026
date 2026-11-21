"""Wykrywanie imion i nazwisk bez modelu językowego: popularne polskie imiona + następujący wyraz wielką literą.

Dopasowanie obejmuje odmianę („Jan Kowalski”, „Jana Kowalskiego”, „Annie Nowak”). Wynik to wyłącznie
podpowiedź do anonimizacji — urzędnik odznacza osoby pełniące funkcje publiczne.
"""
import re

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

_UP = "A-ZŁŚŻŹĆŃÓĘĄ"
_LO = "a-ząćęłńóśźż"


def _stem_pattern(name: str) -> str:
    # Imiona żeńskie na -a: Anna/Anny/Annie/Annę/Anną; męskie: Jan/Jana/Janowi/Janem/Janie;
    # imiona z „e” ruchomym (Marek → Marka) dopuszczamy przez krótszy rdzeń.
    if name.endswith("a"):
        return re.escape(name[:-1]) + f"(?:a|y|i|ie|ę|ą)"
    if name.endswith("ek"):
        return re.escape(name[:-2]) + f"(?:ek|ka|kowi|kiem|ku)"
    return re.escape(name) + f"(?:a|owi|em|ie|u)?"


_FIRST = "|".join(sorted((_stem_pattern(n) for n in FIRST_NAMES), key=len, reverse=True))
PERSON_RE = re.compile(
    rf"\b(?:{_FIRST})\s+[{_UP}][{_LO}]+(?:-[{_UP}][{_LO}]+)?\b"
    rf"|\b[{_UP}]\.\s?[{_UP}][{_LO}]{{2,}}(?:-[{_UP}][{_LO}]+)?\b"  # „E. Góra”
)

# Wyrazy, które po imieniu zwykle nie są nazwiskiem (np. „Jana Pawła II”, „Marii Konopnickiej” jako nazwy ulic
# zostają — urzędnik je odznaczy; tu wykluczamy tylko oczywiste przypadki).
_NOT_SURNAME = {"Miasta", "Urzędu", "Wydziału", "Bydgoszczy", "Bydgoszcz", "Prezydenta", "Rady"}


def find_people(text: str) -> list[tuple[int, int]]:
    spans = []
    for m in PERSON_RE.finditer(text):
        last = m.group(0).split()[-1]
        if last in _NOT_SURNAME:
            continue
        # Nazwa ulicy („ul. Jana Pawła”) to nie osoba — pomijamy, gdy tuż przed stoi „ul.”/„al.”/„pl.”/„os.”.
        if re.search(r"(?:ul|al|pl|os)\.\s*$", text[max(0, m.start() - 6) : m.start()]):
            continue
        spans.append((m.start(), m.end()))
    return spans
