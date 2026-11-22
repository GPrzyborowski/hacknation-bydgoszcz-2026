# Backend — Asystent UDIP

FastAPI + SQLite (FTS5). Swagger UI: http://localhost:8000/docs

## Uruchomienie

```bash
cp .env.example .env          # w katalogu głównym repo, potem wpisz GEMINI_API_KEY
docker compose up --build     # backend :8000, frontend :5173
```

Model językowy: **Google Gemini** przez endpoint zgodny z OpenAI. Wystarczy klucz z
[aistudio.google.com/apikey](https://aistudio.google.com/apikey) w `.env` (`GEMINI_API_KEY=AIza…`).
Po zmianie `.env`: `docker compose up -d --force-recreate backend`.

Bez klucza, a także gdy Gemini nie odpowie lub zgłosi limit zapytań, backend przechodzi na analizę regułową
z ostrzeżeniem — upload nigdy nie wisi. `OFFLINE_MODE=true` blokuje wysyłkę treści do Gemini (403).
Na hackathonie do Gemini trafiają wyłącznie dane testowe organizatora.

### Zmienne środowiskowe

| Zmienna | Domyślnie | Znaczenie |
|---|---|---|
| `GEMINI_API_KEY` | — | klucz Google AI Studio; bez niego analiza regułowa |
| `LLM_MODEL` | `gemini-2.5-flash` | model Gemini |
| `LLM_REASONING_EFFORT` | `none` | wyłącza „myślenie” Gemini 2.5 Flash (szybciej, JSON nie jest ucinany) |
| `LLM_TIMEOUT`, `LLM_MAX_TOKENS`, `LLM_DRAFT_MAX_TOKENS` | `90`, `4096`, `8192` | limity wywołań modelu |
| `LLM_FALLBACK_HEURISTIC` | `true` | przy awarii Gemini analiza regułowa zamiast błędu 502 |
| `OFFLINE_MODE` | `false` | `true` blokuje wysyłkę treści do Gemini |
| `CASE_NUMBER_PREFIX` | `BKS.IV.1431` | prefiks znaku sprawy nadawanego automatycznie |
| `MAX_UPLOAD_MB` | `20` | limit rozmiaru pliku |
| `DEADLINE_SHIFT_TO_WORKING_DAY` | `false` | `true` przesuwa termin z dnia wolnego (art. 57 § 4 KPA) |
| `SEED_DEMO_DATA` | `true` | przy pustej bazie wczytuje dane testowe UMB |
| `LOG_LEVEL` | `INFO` | poziom logowania |

## Budowa

- `domain.py` — statusy spraw, rodzaje pism, statusy wydziałów (wartości kontraktu API).
- `db.py` — schemat, migracje (`PRAGMA user_version`), indeksy FTS5 utrzymywane przez triggery.
- `bootstrap.py` — migracje i dane startowe przy uruchomieniu.
- `routers/` — cienkie endpointy; `services/` — logika: `case_workflow` (tok sprawy), `drafting` (pisma),
  `case_views` (rejestr i karta sprawy), `case_store` (zapis), `dept_tracking` (odpowiedzi wydziałów),
  `deadlines` (terminy ustawowe), `letters` (szablony pism UMB), `analysis` + `llm` (Gemini), `anonymization`,
  `extraction` (PDF/DOCX/OCR), `search` (podobne sprawy), `excel_import`, `documents` (DOCX/PDF).
- Błędy domenowe (`errors.py`) zamienia na odpowiedzi HTTP jeden handler w `main.py`.

## Dane testowe UMB

Przy pierwszym starcie (pusta baza, `SEED_DEMO_DATA=true`) backend wczytuje `app/seed/umb_demo.json`:
10 spraw z rejestru `WNIOSKI O UDOSTĘPNIANIE INFORMACJI PUBLICZNEJ.xlsx` wraz z treścią wniosków, odpowiedzi
BKS (zanonimizowanych przez UMB), pismami kwerendy i doprecyzowania oraz Zarządzenie nr 535/2024 (podzielone na §).
Plik generuje skrypt z folderu materiałów (folder tylko czytany; skany wymagają Tesseract z językiem `pol`):

```bash
python backend/scripts/build_demo_seed.py "C:/Hacknation 2026 - UMB" [--out plik.json]
```

Aby wczytać dane testowe ponownie, usuń `backend/app/data/udip.db`.

Uwagi do danych z rejestru (import ich nie poprawia, tylko oznacza w `date_parse_warning`):
- BKS.IV.1431.15.2026 — data odpowiedzi (14.01.2026) wcześniejsza niż data wpływu (12.09.2026),
- BKS.IV.1431.18.2026 — termin z rokiem 2025 przy wpływie w 2026,
- BKS.IV.1431.509.2026 — termin z dopiskiem „19.08.2026/18.09.2026 - doprecyzowanie wniosku”,
- BKS.IV.1431.543.2026, .590.2026 — odpowiedź po terminie (543: po kwerendzie),
- wniosek BKS.IV.1431.16.2026 to pismo odręczne — OCR go nie odczyta (`extraction.warning`, pole `manual_text`).

## Zasady przyjęte z materiałów UMB

- **Termin** = data wpływu + 14 dni (formuła `=E+14` z rejestru). Termin w dzień wolny jest oznaczany
  (`deadline_note`), nie przesuwany — chyba że `DEADLINE_SHIFT_TO_WORKING_DAY=true`.
- **Przedłużenie** (art. 13 ust. 2 u.d.i.p.) — najwyżej do 2 miesięcy od wpływu; zawiadomienie po upływie
  14 dni jest dopuszczone, ale z ostrzeżeniem.
- **Pozostało dni** = 0 dla spraw zakończonych (jak w rejestrze) + `answered_on_time`.
- **Anonimizacja** — 28 kategorii 1:1 z „Dane podlegające anonimizacji.txt”; dane instytucji (nagłówek BKS,
  e-maile `@*.bydgoszcz.pl`/`@*.gov.pl`, adresy jednostek) nie są proponowane; osoby pełniące funkcje publiczne
  są proponowane jako odznaczone. Maskowanie zawsze wykonuje serwer.
- **Pisma** w układzie BKS UMB: nagłówek, „Bydgoszcz, dnia 14 stycznia 2026 r.”, znak sprawy, „Szanowny Panie/
  Szanowna Pani/Szanowni Państwo”, „Ad 1…”, „Łączę wyrazy szacunku,”, podpis BKS. Szablony kwerendy,
  doprecyzowania i braku dysponenta odtworzone z pism 543, 509, 15 i 17.

## Endpointy

| Metoda | Ścieżka | Opis |
|---|---|---|
| GET | `/` | status, OFFLINE_MODE, model |
| GET | `/api/config` | ustawienia dla interfejsu (prefiks znaku, limity i formaty plików, terminy) |
| GET | `/api/deadlines/preview?received=` | termin odpowiedzi dla daty wpływu (jak przy rejestracji) |
| GET | `/api/deadlines/non-working-days?from=&to=` | soboty, niedziele i święta ustawowe — do kalendarium |
| POST | `/api/intake/analyze` | plik wniosku (+ opcjonalnie `manual_text`) → `parsed_request`, `similar_cases`, `suggested_departments`, `suggested_external_entities`, `suggested_deadline`, jakość OCR, `intake_id` |
| GET | `/api/cases?year=&q=&status=&open_only=` | rejestr od najstarszych, `days_remaining`, `urgency`, stan odpowiedzi wydziałów |
| GET | `/api/cases/years` | lata do przełącznika |
| GET / PATCH / DELETE | `/api/cases/{id}` | karta sprawy (dokumenty, materiały, projekty, historia) / korekta danych / usunięcie |
| POST | `/api/cases/register` | rejestracja po weryfikacji (+ `intake_id`, propozycje próśb do wydziałów) |
| PATCH | `/api/cases/{id}/status` | zmiana statusu; `kwerenda` → termin 2-miesięczny |
| POST | `/api/cases/{id}/department-reply` | materiał z wydziału → projekt pisma (styl UMB, wzór z archiwum) + kandydaci do anonimizacji |
| POST | `/api/cases/{id}/letter` | projekt pisma `kwerenda` / `doprecyzowanie` / `nie_dysponent` / `odpowiedz` (+ status i nowy termin) |
| POST / PATCH / DELETE | `/api/cases/{id}/departments[/{code}]` | zapytanie kolejnego wydziału / status jego odpowiedzi / usunięcie |
| POST | `/api/cases/{id}/departments/{code}/clarification` | prośba do wydziału o uszczegółowienie (treść do skopiowania) |
| POST | `/api/response/generate` | anonimizacja + plik `docx`/`pdf`/`txt`, status `przygotowana_odpowiedz` |
| POST | `/api/response/send` | odnotowanie wysyłki (z `anonymization_items`), zasila archiwum podobnych spraw |
| POST | `/api/response/anonymize-preview` | ponowne wyliczenie kandydatów po edycji treści |
| GET/POST/PUT | `/api/knowledge/rules[/{id}]`, `/rules/import-document` | przepisy, zarządzenia, wzory |
| GET/POST/PUT | `/api/knowledge/anonymization-categories[/{id}]` | kategorie, regexy, maski |
| GET/POST/PUT | `/api/knowledge/departments[/{code}]` | wydziały/biura i słowa kluczowe |
| GET/POST/PUT | `/api/knowledge/external-entities[/{id}]` | podmioty spoza UMB (ZDMiKP, WKZ, Schronisko) dla pism „nie dysponent” |
| POST | `/api/knowledge/cases/manual`, `/cases/import-excel` | archiwum spraw |

Nic nie jest wysyłane automatycznie — ani do wydziałów, ani do wnioskodawców.
