# UDIPilot — materiał dla oceniających

Narzędzie wspiera urzędnika Urzędu Miasta Bydgoszczy w obsłudze wniosków o udostępnienie informacji publicznej:
od wgrania wniosku, przez kalendarz terminów i odpowiedzi wydziałów, po projekt pisma z anonimizacją.
Niczego nie wysyła samo — każdą decyzję podejmuje urzędnik.

**Film (1:31):** [demo/udipilot-film.mp4](demo/udipilot-film.mp4) — wgranie PDF, analiza AI, statusy wydziałów i uszczegółowienie, projekt odpowiedzi z pliku Word, anonimizacja, spis spraw, kalendarz z tabelą.

## Uruchomienie (2 minuty)

```bash
cp .env.example .env          # wpisz GEMINI_API_KEY
docker compose up --build
```

| Co | Adres |
|---|---|
| Aplikacja | http://localhost:5173 |
| Dokumentacja API (Swagger) | http://localhost:8000/docs |
| Specyfikacja OpenAPI w repozytorium | [`docs/openapi.json`](openapi.json) |

Przy pierwszym starcie baza wczytuje 10 spraw z rejestru testowego UMB (z treścią wniosków i odpowiedzi)
oraz Zarządzenie nr 535/2024 podzielone na paragrafy. Plakietka w nagłówku pokazuje używany model Gemini.

## Wymagania wyzwania → rozwiązanie

| Wymaganie z opisu wyzwania | Jak zostało zrealizowane | Gdzie zobaczyć |
|---|---|---|
| 1. Model AI; docelowo model zamknięty, uczący się na wprowadzanych danych | Analiza i projekty pism: Google Gemini przez API zgodne z OpenAI — docelowy model offline podłącza się zmianą `LLM_BASE_URL`, bez zmian w kodzie. `OFFLINE_MODE=true` blokuje wysyłkę treści na zewnątrz. Wiedza (ustawy, zarządzenia, archiwum odpowiedzi) jest w bazie i trafia do promptu — dodanie dokumentu działa od razu, bez trenowania | Baza wiedzy |
| 2. Wgrywanie plików PDF / Word | PDF z warstwą tekstową, DOCX, DOC oraz skany JPG/PNG/TIFF (OCR Tesseract, język polski); przy nieczytelnym skanie urzędnik wpisuje treść ręcznie | Nowy wniosek |
| 3. Kalendarz wniosków: od najstarszych, dni do odpowiedzi, podświetlenie dziś/jutro, statusy, kwerenda, inicjały, Lp., nr, temat, daty, wybór roku | Rejestr ze wszystkimi kolumnami arkusza UMB, przełącznikiem roku i wyszukiwaniem; podświetlenie: po terminie (czerwień), dziś/jutro (bursztyn). Kalendarium miesięczne z dniami wolnymi (święta liczone z Wielkanocy). Termin = wpływ + 14 dni (art. 13 ust. 1), kwerenda do 2 miesięcy (art. 13 ust. 2) | Rejestr wniosków, Kalendarium |
| 4. Anonimizacja: propozycja na szaro, po akceptacji na czarno | 28 kategorii z „Dane podlegające anonimizacji.txt” (wzorce + model); kliknięcie fragmentu przełącza szary ↔ czarny; maski nakłada serwer w pliku DOCX/PDF i w archiwum | Karta sprawy → Projekt pisma |
| 5. Automatyzacja i przeszukiwanie archiwum | Podobne sprawy z archiwum (wyszukiwanie pełnotekstowe FTS5) przy analizie wniosku; gotowe treści próśb do wydziałów; pisma kwerendy, doprecyzowania i braku dysponenta z wzorów UMB | Nowy wniosek → analiza |
| 6. Wskazywanie ścieżki — właściwe wydziały | Propozycje komórek UMB z uzasadnieniem (model + słowa kluczowe + podobne sprawy); podpowiedź, gdy urząd nie jest dysponentem (ZDMiKP, WKZ, schronisko) | Nowy wniosek → Wydziały do zapytania |
| 7. Projekt odpowiedzi z materiałów wydziałów, do sprawdzenia przez urzędnika | Materiał z wydziału (plik lub tekst) → projekt w układzie pism BKS („Ad 1…”, formuły grzecznościowe); braki oznaczone `[DO UZUPEŁNIENIA]` zamiast zmyślonych faktów | Karta sprawy → Odpowiedź z wydziału |
| 9. Brak automatycznej wysyłki | System nic nie wysyła: prośby do wydziałów są do skopiowania, wysyłkę urzędnik tylko odnotowuje | Cała aplikacja |
| 10. Terminowość | Statusy odpowiedzi każdego wydziału, prośba o uszczegółowienie, przedłużenie terminu z kontrolą limitu 2 miesięcy i ostrzeżeniem o spóźnionym zawiadomieniu | Karta sprawy |
| 11. Brak integracji | Działa samodzielnie; import rejestru z arkusza Excel UMB | Baza wiedzy |
| 12. Narzędzie pomocnicze | Każdy wynik modelu jest propozycją do zatwierdzenia lub poprawienia | Cała aplikacja |

## Scenariusz pokazu (ok. 7 minut)

Pliki testowe: folder materiałów wyzwania, `Przykładowe wnioski i odpowiedzi/`.

1. **Rejestr wniosków** — 10 spraw z rejestru UMB, kolumny jak w arkuszu, przełącznik roku, wyszukiwanie
   „Astoria”. Zwróć uwagę na oznaczenia dat budzących wątpliwości (np. termin z rokiem 2025 przy wpływie w 2026).
2. **Kalendarium** — terminy w siatce miesiąca, dni wolne wyszarzone, lista najbliższych terminów.
3. **Nowy wniosek** — wgraj `Wniosek - BKS.IV.1431.590.2026.pdf`. Po kilku sekundach: wnioskodawca, pytania,
   kategoria, uwagi (np. informacja przetworzona), podobne sprawy z archiwum i propozycja wydziałów WIM i WAB.
   Termin liczony od daty wpływu, z ostrzeżeniem, gdy wypada w dzień wolny.
4. **Rejestracja** — zatwierdź dane; system pokazuje gotowe treści próśb do wydziałów (do skopiowania).
5. **Karta sprawy** — w sekcji „Odpowiedź z wydziału” wgraj `Odpowiedź - BKS.IV.1431.590.2026.anonymised.pdf`
   albo wklej treść odpowiedzi wydziału. Powstaje projekt pisma w układzie BKS.
6. **Anonimizacja** — dane osobowe podświetlone na szaro; „Zaczernij propozycje” albo kliknięcie fragmentu;
   pobierz DOCX lub PDF — zaczernione fragmenty są zastąpione maską.
7. **Terminy i wydziały** — status odpowiedzi każdego wydziału, „Poproś o uszczegółowienie”, przedłużenie
   terminu (kwerenda) z wyliczeniem dni i limitem 2 miesięcy.
8. **Skan odręczny** (opcjonalnie) — `Wniosek - BKS.IV.1431.16.2026.pdf`: system rozpoznaje nieczytelny OCR
   i prosi o przepisanie treści zamiast zgadywać.
9. **Swagger** — http://localhost:8000/docs: przepływ sprawy opisany na górze, każdy endpoint z opisem.

## Architektura

```
Przeglądarka (React 19 + TypeScript)  ──HTTP/JSON──>  FastAPI (Python)  ──>  SQLite + FTS5
                                                          │
                                                          ├─ OCR: pdfium + Tesseract (pol)
                                                          ├─ Google Gemini (API zgodne z OpenAI)
                                                          └─ DOCX / PDF: python-docx, fpdf2
```

- Terminy ustawowe, dni wolne, limity plików i maskowanie danych są liczone wyłącznie w backendzie —
  frontend pobiera je przez API, więc reguła jest w jednym miejscu.
- Baza ma migracje schematu, a indeks pełnotekstowy aktualizują triggery.
- Szczegóły: [README](../README.md), [backend/README.md](../backend/README.md), [DESIGN.md](../DESIGN.md).

## Bezpieczeństwo i dane

- Do Gemini trafia wyłącznie treść danych testowych organizatora; `OFFLINE_MODE=true` blokuje wywołania modelu.
- Klucz API jest tylko w `.env` (poza repozytorium).
- Anonimizację wykonuje serwer — do pliku i do archiwum trafia tekst z maskami, nie dane osobowe.
- Brak automatycznej wysyłki i brak integracji z systemami urzędu.
