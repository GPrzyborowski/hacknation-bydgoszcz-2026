"""Wspólne fragmenty wyrażeń regularnych dla polskich tekstów urzędowych."""

PL_UPPER = "A-ZĄĆĘŁŃÓŚŹŻ"
PL_LOWER = "a-ząćęłńóśźż"
PL_LETTER = PL_UPPER + PL_LOWER

CAPITALIZED_WORD = f"[{PL_UPPER}][{PL_LOWER}]+"
EMAIL = r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"
STREET_PREFIX = r"(?:ul|al|os|pl)\."
