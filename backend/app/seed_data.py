"""Dane startowe bazy wiedzy.

- Wydziały i biura UMB: symbole i nazwy z BIP UM Bydgoszczy
  (bip.um.bydgoszcz.pl/artykuly/198/wydzialy, /artykuly/1158/biura, stan na 20.11.2026).
  Słowa kluczowe to heurystyka zespołu do podpowiadania wydziałów — nie pochodzą z BIP
  i można je edytować z UI (/api/knowledge/departments).
  Uzupełnione o zakresy z materiałów UMB (które wydziały przygotowały odpowiedzi w sprawach testowych).
- Kategorie anonimizacji: dokładnie lista „Dane podlegające anonimizacji.txt” z materiałów UMB.
- Podmioty zewnętrzne: dane kontaktowe z pism UMB, w których urząd nie był dysponentem informacji.
- Reguły: streszczenia przepisów u.d.i.p. i KPA + odnośniki z materiałów UMB. Pełny tekst Zarządzenia
  nr 535/2024 wczytywany jest z seed/umb_demo.json; kolejne akty — /api/knowledge/rules/import-document.
"""

MASK = "[ANONIMIZACJA]"
NAME_CATEGORY = "Imię i nazwisko osoby fizycznej (niepełniącej funkcji publicznej)"

DEPARTMENTS: list[tuple[str, str, str]] = [
    ("WAB", "Wydział Administracji Budowlanej", "dokumentacja budowlana, projekt zagospodarowania terenu, akta sprawy budowlanej, apartamentowiec, pozwolenie na budowę, budowa, budynek, rozbiórka, zgłoszenie robót, nadzór budowlany, projekt budowlany, użytkowanie obiektu"),
    ("WE", "Wydział Edukacji i Sportu", "liczba uczniów, uczniowie, cudzoziemcy w szkołach, szkoły podstawowe, szkoła, przedszkole, oświata, nauczyciel, edukacja, sport, obiekty sportowe, klub sportowy, stypendium, basen"),
    ("WF", "Wydział Funduszy Europejskich", "fundusze europejskie, unijne, dofinansowanie, dotacja UE, projekt unijny, KPO"),
    ("WGO", "Wydział Gospodarki Odpadami", "opłata za gospodarowanie odpadami, deklaracje śmieciowe, liczba mieszkańców według deklaracji, odpady, śmieci, wywóz, segregacja, opłata śmieciowa, PSZOK, recykling"),
    ("WI", "Wydział Informatyki", "system informatyczny, oprogramowanie, sprzęt komputerowy, licencja, serwer, IT"),
    ("WIM", "Wydział Inwestycji Miasta", "kierownik robót, dziennik budowy, aneks do umowy z wykonawcą, Astoria, inwestycja, remont, przebudowa, budowa drogi, ulica, wykonawca, koszt inwestycji, modernizacja, kompleks"),
    ("WK", "Wydział Księgowości", "księgowość, faktura, płatność, wydatki, rozliczenie finansowe, wynagrodzenie, koszty"),
    ("WMG", "Wydział Mienia i Geodezji", "nieruchomość, działka, grunt, sprzedaż nieruchomości, dzierżawa, najem, geodezja, mapa, użytkowanie wieczyste"),
    ("WOŚ", "Wydział Ochrony Środowiska", "środowisko, wycinka drzew, hałas, powietrze, smog, decyzja środowiskowa, zwierzęta, woda"),
    ("WOA", "Wydział Organizacyjno-Administracyjny", "organizacja urzędu, regulamin organizacyjny, zarządzenie prezydenta, kadry, zatrudnienie, etaty, samochody służbowe, umowy urzędu"),
    ("WPL", "Wydział Podatków i Opłat Lokalnych", "podatek od nieruchomości, podatek, opłata lokalna, ulga podatkowa, umorzenie podatku, opłata targowa"),
    ("WSO", "Wydział Spraw Obywatelskich", "punkty sprzedaży alkoholu, zezwolenia na sprzedaż alkoholu, dowód osobisty, meldunek, ewidencja ludności, działalność gospodarcza, CEIDG, zgromadzenia, stowarzyszenia"),
    ("WSR", "Wydział Świadczeń Rodzinnych", "świadczenia rodzinne, zasiłek, alimenty, fundusz alimentacyjny, świadczenie, karta dużej rodziny"),
    ("WUK", "Wydział Uprawnień Komunikacyjnych", "prawo jazdy, rejestracja pojazdu, pojazd, tablice rejestracyjne, licencja taxi, transport drogowy"),
    ("WW", "Wydział Windykacji", "windykacja, zaległości, egzekucja, dłużnik, należności, wierzytelności"),
    ("WZP", "Wydział Zamówień Publicznych", "zamówienie publiczne, przetarg, postępowanie przetargowe, oferta, SWZ, umowa z wykonawcą"),
    ("WZB", "Wydział Zarządzania Budżetem Miasta", "budżet miasta, uchwała budżetowa, wydatki budżetowe, dochody, zadłużenie, kredyt, obligacje, WPF"),
    ("WZK", "Wydział Zarządzania Kryzysowego i Ochrony Ludności", "zarządzanie kryzysowe, obrona cywilna, schron, powódź, ochrona ludności, alarm"),
    ("WGK", "Wydział Zieleni i Gospodarki Komunalnej", "bezdomne zwierzęta, odławianie zwierząt, opieka nad zwierzętami, schronisko, zieleń, park, drzewa, nasadzenia, gospodarka komunalna, cmentarz, plac zabaw, oświetlenie"),
    ("BAS", "Biuro Aktywności Społecznej", "organizacje pozarządowe, NGO, budżet obywatelski, konsultacje społeczne, rady osiedli, dotacje dla organizacji"),
    ("BCB", "Biuro Cyfryzacji i Bezpieczeństwa Informacji", "cyfryzacja, bezpieczeństwo informacji, ochrona danych osobowych, RODO, monitoring, cyberbezpieczeństwo"),
    ("BZS", "Biuro ds. Zdrowia i Polityki Społecznej", "zdrowie, szpital, profilaktyka, pomoc społeczna, seniorzy, niepełnosprawni, uzależnienia"),
    ("BKS", "Biuro Komunikacji Społecznej", "skargi, petycje, komunikacja z mieszkańcami, konsultacje"),
    ("BKZ", "Biuro Konserwatora Zabytków", "zabytek, konserwator, rejestr zabytków, ochrona zabytków, kamienica, renowacja"),
    ("BKB", "Biuro Kultury Bydgoskiej", "kultura, teatr, muzeum, festiwal, wydarzenie kulturalne, instytucja kultury, biblioteka"),
    ("BPR", "Biuro Prasowe", "prasa, media, rzecznik prasowy, komunikat, wywiad"),
    ("BP", "Biuro Promocji Miasta i Współpracy z Zagranicą", "promocja miasta, reklama, kampania promocyjna, miasta partnerskie, wydarzenia promocyjne, sponsoring"),
    ("BRM", "Biuro Rady Miasta", "rada miasta, radny, sesja, uchwała rady, interpelacja, komisja rady, diety radnych"),
    ("BZIT", "Biuro ZIT", "zintegrowane inwestycje terytorialne, ZIT, obszar funkcjonalny"),
]

# (nazwa, podstawa prawna, regex lub None, maska)
# Lista kategorii 1:1 wg „Dane podlegające anonimizacji.txt” (materiały UMB). Regexy podpowiadają fragmenty
# do zaczernienia — kategorie bez regexu wskazuje model językowy lub urzędnik.
ANONYMIZATION_CATEGORIES: list[tuple[str, str, str | None, str]] = [
    (NAME_CATEGORY, "art. 5 ust. 2 u.d.i.p.", None, MASK),
    ("Numer PESEL", "art. 5 ust. 2 u.d.i.p.; art. 87 RODO", r"\b\d{11}\b", MASK),
    ("Numer i seria dowodu osobistego lub innego dokumentu tożsamości", "art. 5 ust. 2 u.d.i.p.",
     r"\b[A-Z]{3}\s?\d{6}\b|\b[A-Z]{2}\s?\d{7}\b", MASK),
    ("Numer NIP osoby fizycznej nieprowadzącej działalności gospodarczej", "art. 5 ust. 2 u.d.i.p.",
     r"\bNIP\b[:\s]*\d{3}[- ]?\d{2,3}[- ]?\d{2}[- ]?\d{2,3}\b", MASK),
    ("Data i miejsce urodzenia", "art. 5 ust. 2 u.d.i.p.",
     r"(?i:\bur(?:\.|odzon[ya]))\s+(?:dnia\s+)?\d{1,2}[./-]\d{1,2}[./-]\d{4}(?:\s*r\.)?(?:\s+w\s+[A-ZŁŚŻŹĆŃÓĘĄ][a-ząćęłńóśźż]+)?", MASK),
    ("Adres zamieszkania, zameldowania lub korespondencyjny osoby fizycznej", "art. 5 ust. 2 u.d.i.p.",
     # Nazwa ulicy (1–3 wyrazy wielką literą) i od razu numer domu — "ul. Gdańskiej w 2024" nie pasuje.
     r"\b(?:ul|al|os|pl)\.\s*(?:[A-ZŁŚŻŹĆŃÓĘĄ0-9][\wąćęłńóśźżĄĆĘŁŃÓŚŹŻ.\-]*\s+){1,3}\d{1,4}[a-zA-Z]?(?:\s*/\s*\d+|\s+m\.\s*\d+)?\b"
     r"(?:,?\s*\d{2}\s?-\s?\d{3}\s+[A-ZŁŚŻŹĆŃÓĘĄ][a-ząćęłńóśźżA-ZŁŚŻŹĆŃÓĘĄ]+)?", MASK),
    ("Prywatny numer telefonu", "art. 5 ust. 2 u.d.i.p.",
     r"(?<!\d)(?:\+48[ -]?)?(?:\d{3}[ -]?\d{3}[ -]?\d{3}|\(?\d{2}\)?[ -]?\d{3}[ -]?\d{2}[ -]?\d{2})(?!\d)", MASK),
    ("Prywatny adres poczty elektronicznej (e-mail)", "art. 5 ust. 2 u.d.i.p.", r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", MASK),
    ("Numer rachunku bankowego osoby fizycznej", "art. 5 ust. 2 u.d.i.p.", r"\b(?:PL\s?)?\d{2}(?:[ ]?\d{4}){6}\b", MASK),
    ("Własnoręczny podpis (parafka) osoby niepełniącej funkcji publicznej", "art. 5 ust. 2 u.d.i.p.", None, MASK),
    ("Wizerunek osoby fizycznej niepełniącej funkcji publicznej", "art. 5 ust. 2 u.d.i.p.", None, MASK),
    ("Stan cywilny i sytuacja rodzinna (np. liczba dzieci, imiona rodziców)", "art. 5 ust. 2 u.d.i.p.",
     r"(?i)\b(?:żonat[ya]?|zamężn[aą]|rozwiedzion[ya]|wdow(?:a|iec)|imiona rodziców|imię (?:ojca|matki)|liczb[aęy] dzieci)\b", MASK),
    ("Dane dotyczące stanu zdrowia, niepełnosprawności lub nałogów", "art. 5 ust. 2 u.d.i.p.; art. 9 RODO",
     r"(?i)\b(?:niepełnospraw\w*|chorob\w*|chory|chora|diagnoz\w*|leczeni\w*|uzależni\w*|alkoholi[kz]\w*|hospitaliz\w*)\b", MASK),
    ("Dane o sytuacji majątkowej, dochodach i zadłużeniu osoby fizycznej", "art. 5 ust. 2 u.d.i.p.",
     r"(?i)\b(?:zadłużen\w*|zaległoś\w* w opłatach|egzekucj\w* komornicz\w*|dochód (?:wnioskodawc|rodzin|gospodarstw)\w*)\b", MASK),
    ("Informacje o korzystaniu ze świadczeń pomocy społecznej", "art. 5 ust. 2 u.d.i.p.",
     r"(?i)\b(?:korzysta\w* (?:ze? )?(?:świadczeń|pomocy społecznej|zasiłk\w*)|pobiera\w* (?:zasiłek|świadczeni\w*))\b", MASK),
    ("Dane dotyczące poglądów politycznych, przekonań religijnych lub światopoglądowych", "art. 5 ust. 2 u.d.i.p.; art. 9 RODO", None, MASK),
    ("Informacje o przynależności związkowej lub partyjnej", "art. 5 ust. 2 u.d.i.p.; art. 9 RODO",
     r"(?i)\bczłon\w* (?:partii|związku zawodowego)\b[^.,;\n]{0,40}", MASK),
    ("Dane o pochodzeniu rasowym lub etnicznym", "art. 5 ust. 2 u.d.i.p.; art. 9 RODO", None, MASK),
    ("Dane o orientacji seksualnej", "art. 5 ust. 2 u.d.i.p.; art. 9 RODO", None, MASK),
    ("Informacje o karalności, wyrokach skazujących i naruszeniach prawa", "art. 5 ust. 2 u.d.i.p.; art. 10 RODO",
     r"(?i)\b(?:karan[ya]|niekaran[ya]|skazan[ya]|wyrok\w* skazując\w*|karalnoś\w*)\b", MASK),
    ("Numer księgi wieczystej (jeśli pozwala na bezpośrednią identyfikację konkretnej osoby fizycznej)", "art. 5 ust. 2 u.d.i.p.",
     r"\b[A-Z]{2}\d[A-Z]/\d{8}/\d\b", MASK),
    ("Numer działki ewidencyjnej (w sytuacjach, gdy umożliwia łatwe ustalenie tożsamości prywatnego właściciela)", "art. 5 ust. 2 u.d.i.p.",
     r"(?i)\bdział\w*\s+(?:ewidencyjn\w*\s+)?(?:nr|numer)\s*\d+(?:/\d+)?", MASK),
    ("Numer rejestracyjny pojazdu prywatnego", "art. 5 ust. 2 u.d.i.p.",
     r"\bC[A-Z]{1,2}\s?(?=[0-9A-Z]{4,5}\b)[A-Z]{0,2}\d[0-9A-Z]{2,4}\b", MASK),
    ("Tajemnica przedsiębiorstwa (dane techniczne, technologiczne, organizacyjne lub handlowe firmy)", "art. 5 ust. 2 u.d.i.p.; art. 11 ust. 2 u.z.n.k.", None, MASK),
    ("Tajemnica skarbowa (indywidualne dane podatników)", "art. 5 ust. 1 u.d.i.p.; art. 293 Ordynacji podatkowej", None, MASK),
    ("Tajemnica bankowa i ubezpieczeniowa", "art. 5 ust. 1 u.d.i.p.; art. 104 Prawa bankowego", None, MASK),
    ("Dane objęte tajemnicą ustawowo chronioną (np. tajemnica zawodowa, lekarska, adwokacka)", "art. 5 ust. 1 u.d.i.p.", None, MASK),
    ("Informacje niejawne (klauzule poufności)", "art. 5 ust. 1 u.d.i.p.; ustawa o ochronie informacji niejawnych",
     r"\b(?:ZASTRZEŻONE|POUFNE|ŚCIŚLE TAJNE|TAJNE)\b", MASK),
]

# Dane instytucji publicznych NIE podlegają anonimizacji (nagłówek UMB, podmioty wskazywane w pismach).
# Kandydat do anonimizacji jest pomijany, jeśli jego treść pasuje do któregoś wzorca.
ANONYMIZATION_EXEMPT_PATTERNS: list[str] = [
    r"@(?:[\w-]+\.)*(?:bydgoszcz\.pl|gov\.pl)$",            # e-maile urzędów i jednostek miejskich
    r"^(?:ul\.\s*)?Jezuicka\s+[12]\b",                       # siedziba BKS UMB i delegatury WKZ
    r"^(?:ul\.\s*)?Toruńska\s+174a\b",                       # ZDMiKP
    r"^(?:ul\.\s*)?Grunwaldzka\s+298\b",                     # Schronisko dla Zwierząt
    r"^(?:ul\.\s*)?Królowej Jadwigi\s+23\b",                 # kompleks Astoria (obiekt miejski)
    r"^\(?\+?(?:48\s*0?\s*)?\(?52\)?[\s-]*(?:58[\s-]*58[\s-]*(?:365|623)|322[\s-]*4[49][\s-]*(?:17|98))$",  # tel. BKS, WKZ
]

# Podmioty, do których UMB odsyła wnioskodawcę, gdy nie jest dysponentem informacji
# (dane kontaktowe dosłownie z pism BKS.IV.1431.15.2026, .17.2026, .293.2025 — materiały wyzwania).
# (nazwa, nazwa w dopełniaczu, dane kontaktowe, słowa kluczowe)
EXTERNAL_ENTITIES: list[tuple[str, str, str, str]] = [
    ("Kujawsko-Pomorski Wojewódzki Konserwator Zabytków, Delegatura w Bydgoszczy",
     "Kujawsko-Pomorskiego Wojewódzkiego Konserwatora Zabytków",
     "Kujawsko-Pomorski Wojewódzki Konserwator Zabytków\nDelegatura w Bydgoszczy\nul. Jezuicka 2\n85-102 BYDGOSZCZ\n"
     "tel. (+48 0 52) 322 44 17, 322 49 98\ne-mail: bydgoszcz@torun.wkz.gov.pl",
     "rzeźba, pomnik, zabytek, rejestr zabytków"),
    ("Zarząd Dróg Miejskich i Komunikacji Publicznej w Bydgoszczy",
     "Zarządu Dróg Miejskich i Komunikacji Publicznej w Bydgoszczy",
     "Zarząd Dróg Miejskich i Komunikacji Publicznej w Bydgoszczy\nul. Toruńska 174a\n85-844 Bydgoszcz\n"
     "e-mail: zarzad@zdmikp.bydgoszcz.pl",
     "drogi, ulice, komunikacja miejska, tramwaje, autobusy, parkowanie, sygnalizacja, ZDMiKP"),
    ("Schronisko dla Zwierząt w Bydgoszczy",
     "Schroniska dla Zwierząt w Bydgoszczy",
     "Schronisko dla Zwierząt w Bydgoszczy\nul. Grunwaldzka 298\n85-438 Bydgoszcz",
     "schronisko, bezdomne zwierzęta, psy, koty, adopcja"),
]

# (tytuł, źródło, treść)
RULES: list[tuple[str, str, str]] = [
    ("Termin udostępnienia informacji", "u.d.i.p. art. 13",
     "Informację publiczną udostępnia się bez zbędnej zwłoki, nie później niż w terminie 14 dni od dnia złożenia wniosku. "
     "Jeżeli nie może być udostępniona w tym terminie, organ powiadamia wnioskodawcę o powodach opóźnienia oraz o terminie, "
     "w jakim udostępni informację, nie dłuższym niż 2 miesiące od dnia złożenia wniosku."),
    ("Ograniczenie ze względu na prywatność i tajemnicę przedsiębiorcy", "u.d.i.p. art. 5 ust. 2",
     "Prawo do informacji publicznej podlega ograniczeniu ze względu na prywatność osoby fizycznej lub tajemnicę przedsiębiorcy. "
     "Ograniczenie nie dotyczy informacji o osobach pełniących funkcje publiczne, mających związek z pełnieniem tych funkcji, "
     "w tym o warunkach powierzenia i wykonywania funkcji, oraz przypadku, gdy osoba fizyczna lub przedsiębiorca rezygnują z przysługującego im prawa."),
    ("Informacja przetworzona", "u.d.i.p. art. 3 ust. 1 pkt 1",
     "Prawo do uzyskania informacji przetworzonej przysługuje w takim zakresie, w jakim jest to szczególnie istotne dla interesu publicznego. "
     "Wnioskodawca powinien wykazać szczególną istotność dla interesu publicznego; w razie jej braku organ wydaje decyzję odmowną."),
    ("Odmowa udostępnienia — decyzja", "u.d.i.p. art. 16",
     "Odmowa udostępnienia informacji publicznej oraz umorzenie postępowania o udostępnienie informacji w przypadku, o którym mowa w art. 14 ust. 2, "
     "przez organ władzy publicznej następują w drodze decyzji. Do decyzji stosuje się przepisy KPA z modyfikacjami z art. 16 ust. 2."),
    ("Sposób i forma udostępnienia", "u.d.i.p. art. 14",
     "Udostępnianie informacji na wniosek następuje w sposób i w formie zgodnych z wnioskiem, chyba że środki techniczne nie umożliwiają tego. "
     "Wówczas organ powiadamia pisemnie wnioskodawcę o przyczynach i wskazuje, w jaki sposób lub w jakiej formie informacja może być udostępniona niezwłocznie. "
     "Jeżeli w terminie 14 dni od powiadomienia wnioskodawca nie złoży wniosku o udostępnienie w sposób lub formie wskazanych, postępowanie umarza się."),
    ("Informacja dostępna w BIP", "u.d.i.p. art. 10 ust. 1",
     "Informacja publiczna, która nie została udostępniona w Biuletynie Informacji Publicznej lub centralnym repozytorium, jest udostępniana na wniosek. "
     "Jeżeli żądana informacja jest opublikowana w BIP, w odpowiedzi można wskazać link do publikacji."),
    ("Organ niebędący dysponentem informacji", "orzecznictwo do u.d.i.p. art. 4",
     "Jeżeli organ nie dysponuje żądaną informacją, informuje o tym wnioskodawcę pismem (nie w drodze decyzji). "
     "Nie ma obowiązku przekazywania wniosku według właściwości, można jednak wskazać podmiot, który może dysponować informacją."),
    ("Wezwanie do usunięcia braków (doprecyzowania) wniosku", "KPA art. 64 § 2 (streszczenie)",
     "Jeżeli podanie nie spełnia wymagań, wzywa się wnoszącego do usunięcia braków w wyznaczonym terminie, nie krótszym niż 7 dni, "
     "z pouczeniem, że nieusunięcie braków spowoduje pozostawienie podania bez rozpoznania. W praktyce UMB (pismo BKS.IV.1431.509.2026) "
     "wezwanie do doprecyzowania zakresu wniosku zawiera termin 7 dni i jednocześnie wyznacza nowy termin rozpatrzenia (art. 13 ust. 2 u.d.i.p.)."),
    ("Ustawa o dostępie do informacji publicznej — tekst", "https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=wdu20011121198",
     "Ustawa z dnia 6 września 2001 r. o dostępie do informacji publicznej (t.j. Dz. U. z 2022 r. poz. 902 z późn. zm.). "
     "Pełny tekst w ISAP — wgraj PDF przez import dokumentu, aby był przeszukiwany lokalnie."),
    ("Kodeks postępowania administracyjnego — tekst", "https://isap.sejm.gov.pl/isap.nsf/DocDetails.xsp?id=wdu19600300168",
     "Ustawa z dnia 14 czerwca 1960 r. Kodeks postępowania administracyjnego. Stosowany m.in. do decyzji o odmowie udostępnienia "
     "informacji (art. 16 ust. 2 u.d.i.p.) oraz liczenia terminów (art. 57 KPA). Pełny tekst w ISAP."),
    ("Instrukcja udostępniania informacji publicznej UMB", "https://bip.um.bydgoszcz.pl/artykul/1052/2/udostepnianie-informacji-publicznej",
     "Instrukcja Urzędu Miasta Bydgoszczy dla wnioskodawców — zasady składania wniosków o udostępnienie informacji publicznej."),
    ("Struktura organizacyjna Urzędu Miasta Bydgoszczy", "https://bip.um.bydgoszcz.pl/artykul/2/3/urzad-miasta",
     "Wydziały i biura UMB (lista w bazie wiedzy: /api/knowledge/departments) — podstawa wskazywania komórek merytorycznych."),
    ("Wzór pisma — odpowiedź na wniosek", "pisma BKS UMB z materiałów wyzwania",
     "Układ: nagłówek BKS, „Bydgoszcz, dnia 14 stycznia 2026 r.”, znak sprawy, zwrot „Szanowny Panie, / Szanowna Pani, / Szanowni Państwo,”. "
     "Treść: „w odpowiedzi na wystosowany przez Pana wniosek o udostępnienie informacji publicznej w zakresie …, na podstawie materiału "
     "przygotowanego przez komórkę merytoryczną, tj. Wydział … Urzędu Miasta Bydgoszczy informuję, co następuje.” Następnie odpowiedzi "
     "„Ad 1”, „Ad 2”… w kolejności pytań, ewentualnie „Załącznik:”. Zakończenie: „Łączę wyrazy szacunku,” i podpis "
     "„Biuro Komunikacji Społecznej, Urząd Miasta Bydgoszczy”. Nie dopisuje się informacji, których nie przekazały wydziały."),
]
