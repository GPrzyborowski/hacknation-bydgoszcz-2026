# Asystent UDIP — Hacknation Bydgoszcz 2026

Asystent do obsługi wniosków o udostępnienie informacji publicznej w Urzędzie Miasta Bydgoszczy: odczyt wniosku
(PDF, Word, skan z OCR), analiza modelem Google Gemini, rejestr i kalendarium terminów, odpowiedzi wydziałów,
projekty pism w układzie BKS z anonimizacją oraz eksportem DOCX i PDF. Nic nie jest wysyłane automatycznie —
decyzje podejmuje urzędnik.

## Uruchomienie

```bash
cp .env.example .env          # wpisz GEMINI_API_KEY
docker compose up --build
```

- aplikacja: http://localhost:5173
- API i dokumentacja Swagger: http://localhost:8000/docs

## Struktura

- `backend/` — FastAPI + SQLite (FTS5). Zmienne środowiskowe, zasady przyjęte z materiałów UMB i lista
  endpointów: [backend/README.md](backend/README.md).
- `frontend/` — React 19 + TypeScript + Vite:
  - `src/lib/` — klient API (`api.ts`), ustawienia z backendu (`config.ts`), hooki danych (`hooks.ts`),
    etykiety i reguły prezentacji (`domain.ts`), daty, pliki, routing;
  - `src/components/` — elementy wspólne: strefa upuszczania pliku, komunikaty, przyciski;
  - `src/views/` — ekrany: `intake/` (nowy wniosek), `case/` (karta sprawy), rejestr, kalendarium, baza wiedzy.
- `DESIGN.md`, `PRODUCT.md` — system wizualny i założenia produktu.

Terminy ustawowe, dni wolne od pracy, limity plików i maskowanie danych są liczone wyłącznie w backendzie;
frontend pobiera je przez API (`/api/config`, `/api/deadlines/*`).

## Kontrola jakości

```bash
cd frontend && npx tsc -b && npm run lint
```
