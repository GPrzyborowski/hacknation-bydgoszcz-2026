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
    yield
    llm.close()


app = FastAPI(
    title="Asystent UDIP — API",
    description=(
        "Obsługa wniosków o udostępnienie informacji publicznej w Urzędzie Miasta Bydgoszczy. "
        "API przygotowuje materiały i podpowiedzi, ale niczego samo nie wysyła — ani do wydziałów, "
        "ani do wnioskodawców. Ostateczną decyzję podejmuje urzędnik."
    ),
    version="0.2.0",
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
