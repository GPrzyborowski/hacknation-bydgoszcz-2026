# Backend — Asystent UDIP

FastAPI + SQLite (FTS5). Swagger UI: http://localhost:8000/docs

## Uruchomienie

```bash
cp .env.example .env          # w katalogu głównym repo
docker compose up --build     # backend :8000, frontend :5173
```

Bez `LLM_BASE_URL` backend działa w **trybie heurystycznym** (ekstrakcja regułowa, szablon pisma) —
cały workflow da się przejść bez modelu. Z lokalnym modelem:

```bash
docker compose --profile llm up -d ollama
docker compose exec ollama ollama pull qwen2.5:7b-instruct-q4_K_M
# .env: LLM_BASE_URL=http://ollama:11434/v1
```

`OFFLINE_MODE=true` (domyślnie) blokuje wywołanie LLM spoza sieci lokalnej (HTTP 403).

## Dane testowe UMB

Przy pierwszym starcie (pusta baza, `SEED_DEMO_DATA=true`) backend wczytuje `app/seed/umb_demo.json`:
10 spraw z rejestru `WNIOSKI O UDOSTĘPNIANIE INFORMACJI PUBLICZNEJ.xlsx` wraz z treścią wniosków, odpowiedzi
BKS (zanonimizowanych przez UMB), pismami kwerendy i doprecyzowania oraz Zarządzenie nr 535/2024 (podzielone na §).
Plik generuje skrypt z folderu materiałów (folder tylko czytany; skany wymagają Tesseract z językiem `pol`):

```bash
python backend/scripts/build_demo_seed.py "C:/Hacknation 2026 - UMB"
```

Aby wczytać seed ponownie, usuń `backend/app/data/udip.db`.

Uwagi do danych z rejestru (import ich nie poprawia, tylko oznacza w `date_parse_warning`):
- BKS.IV.1431.15.2026 — data odpowiedzi (14.01.2026) wcześniejsza niż data wpływu (12.09.2026),
- BKS.IV.1431.18.2026 — termin z rokiem 2025 przy wpływie w 2026,
- BKS.IV.1431.509.2026 — termin z dopiskiem „19.08.2026/18.09.2026 - doprecyzowanie wniosku”,
- BKS.IV.1431.543.2026, .590.2026 — odpowiedź po terminie (543: po kwerendzie),
- wniosek BKS.IV.1431.16.2026 to pismo odręczne — OCR go nie odczyta (`extraction.warning`, pole `manual_text`).

## Zasady przyjęte z materiałów UMB

- **Termin** = data wpływu + 14 dni (formuła `=E+14` z rejestru). Termin w dzień wolny jest oznaczany
  (`deadline_note`), nie przesuwany — chyba że `DEADLINE_SHIFT_TO_WORKING_DAY=true` (art. 57 § 4 KPA).
- **Pozostało dni** = 0 dla spraw zakończonych (jak w rejestrze) + `answered_on_time`.
- **Anonimizacja** — 28 kategorii 1:1 z „Dane podlegające anonimizacji.txt”; dane instytucji (nagłówek BKS,
  e-maile `@*.bydgoszcz.pl`/`@*.gov.pl`, adresy jednostek) nie są proponowane; osoby pełniące funkcje publiczne
  są proponowane jako odznaczone.
- **Pisma** w układzie BKS UMB: nagłówek, „Bydgoszcz, dnia 14 stycznia 2026 r.”, znak sprawy, „Szanowny Panie/
  Szanowna Pani/Szanowni Państwo”, „Ad 1…”, „Łączę wyrazy szacunku,”, podpis BKS. Szablony kwerendy,
  doprecyzowania i braku dysponenta odtworzone z pism 543, 509, 15 i 17.

## Endpointy

| Metoda | Ścieżka | Opis |
|---|---|---|
| GET | `/` | status, OFFLINE_MODE, model |
| POST | `/api/intake/analyze` | plik wniosku (+ opcjonalnie `manual_text`) → `parsed_request`, `similar_cases`, `suggested_departments`, `suggested_external_entities`, `suggested_deadline`, jakość OCR, `intake_id` |
| GET | `/api/cases?year=&q=&status=` | rejestr od najstarszych, `days_remaining`, `urgency` (podświetlenie) |
| GET | `/api/cases/years` | lata do przełącznika |
| GET / PATCH / DELETE | `/api/cases/{id}` | szczegóły (materiały, projekty, historia) / korekta danych / usunięcie |
| POST | `/api/cases/register` | rejestracja po weryfikacji (+ `intake_id`, szablony próśb do wydziałów) |
| PATCH | `/api/cases/{id}/status` | zmiana statusu; `kwerenda` → termin 2-miesięczny |
| POST | `/api/cases/{id}/department-reply` | materiał z wydziału → projekt pisma (styl UMB, wzór z archiwum) + kandydaci do anonimizacji |
| POST | `/api/cases/{id}/letter` | projekt pisma `kwerenda` / `doprecyzowanie` / `nie_dysponent` / `odpowiedz` (+ status i nowy termin) |
| POST | `/api/response/generate` | anonimizacja + plik `docx`/`pdf`/`txt`, status `przygotowana_odpowiedz` |
| POST | `/api/response/send` | oznaczenie wysyłki, zasila archiwum (`cases_fts`) |
| POST | `/api/response/anonymize-preview` | ponowne wyliczenie kandydatów po edycji treści |
| GET/POST/PUT | `/api/knowledge/rules[/{id}]`, `/rules/import-document` | przepisy, zarządzenia, wzory |
| GET/POST/PUT | `/api/knowledge/anonymization-categories[/{id}]` | kategorie, regexy, maski |
| GET/POST/PUT | `/api/knowledge/departments[/{code}]` | wydziały/biura i słowa kluczowe |
| GET/POST/PUT | `/api/knowledge/external-entities[/{id}]` | podmioty spoza UMB (ZDMiKP, WKZ, Schronisko) dla pism „nie dysponent” |
| POST | `/api/knowledge/cases/manual`, `/cases/import-excel` | archiwum spraw |

Nic nie jest wysyłane automatycznie — ani do wydziałów, ani do wnioskodawców.
