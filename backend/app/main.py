import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import bootstrap
import config
from errors import AppError
from routers import cases, intake, knowledge, response, system
from services import llm

logging.basicConfig(level=config.LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# Biblioteki, które na poziomie INFO logują każde zapytanie do Gemini i każde osadzenie fontu w PDF.
for noisy_logger in ("httpx", "fontTools"):
    logging.getLogger(noisy_logger).setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(_: FastAPI):
    bootstrap.init_database()
    if not llm.enabled():
        logging.getLogger(__name__).error("Brak GEMINI_API_KEY — analiza wniosków i projekty pism będą niedostępne.")
    yield
    llm.close()


API_DESCRIPTION = """
Obsługa wniosków o udostępnienie informacji publicznej (u.d.i.p.) w Urzędzie Miasta Bydgoszczy.
API przygotowuje materiały i podpowiedzi, ale **niczego samo nie wysyła** — ani do wydziałów, ani do
wnioskodawców. Ostateczną decyzję zawsze podejmuje urzędnik.

### Przepływ sprawy
1. **Przyjęcie** — `POST /api/intake/analyze`: odczyt pliku (PDF, Word, skan z OCR), analiza modelem Gemini,
   podobne sprawy z archiwum, propozycja wydziałów i termin. Nic jeszcze nie jest rejestrowane.
2. **Rejestracja** — `POST /api/cases/register`: sprawa trafia do rejestru z terminem 14 dni
   (art. 13 ust. 1 u.d.i.p.) i treścią próśb do wydziałów do skopiowania.
3. **Wydziały** — `POST /api/cases/{id}/department-reply`: materiał z wydziału → projekt odpowiedzi w układzie
   pism BKS z kandydatami do anonimizacji. Statusy wydziałów i prośby o uszczegółowienie: `/departments`.
4. **Pisma w toku** — `POST /api/cases/{id}/letter`: kwerenda (przedłużenie do 2 miesięcy, art. 13 ust. 2),
   wezwanie do doprecyzowania, wskazanie właściwego podmiotu.
5. **Odpowiedź** — `POST /api/response/generate` (DOCX/PDF z maskami), `POST /api/response/send`
   (odnotowanie wysyłki, zanonimizowana treść zasila archiwum podobnych spraw).

### Szybki test
`GET /api/cases` zwraca 10 spraw testowych UMB wczytanych przy pierwszym starcie. Plik wniosku do
`/api/intake/analyze` można wysłać przyciskiem **Try it out**.
"""

TAGS = [
    {"name": "0. System", "description": "Stan backendu, ustawienia dla interfejsu, terminy i dni wolne."},
    {"name": "1. Przyjęcie wniosku", "description": "Odczyt i analiza wniosku przed rejestracją."},
    {"name": "2. Rejestr wniosków", "description": "Sprawy, statusy, wydziały i pisma w toku sprawy."},
    {"name": "3. Odpowiedź i anonimizacja", "description": "Pliki pism z anonimizacją i odnotowanie wysyłki."},
    {"name": "4. Baza wiedzy", "description": "Przepisy, kategorie anonimizacji, wydziały, podmioty zewnętrzne i archiwum."},
]

app = FastAPI(
    title="UDIPilot — API",
    description=API_DESCRIPTION,
    version="1.0.0",
    openapi_tags=TAGS,
    swagger_ui_parameters={"docExpansion": "list", "tryItOutEnabled": True, "displayRequestDuration": True},
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.exception_handler(AppError)
def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
    return JSONResponse({"detail": exc.message}, status_code=exc.status_code)


for module in (system, intake, cases, response, knowledge):
    app.include_router(module.router)
