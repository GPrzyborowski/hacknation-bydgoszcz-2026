"""Asystent UDIP — backend (UM Bydgoszczy).

Zasada human-in-the-loop: API przygotowuje materiały i podpowiedzi, ale niczego samo nie wysyła
— ani do wydziałów, ani do wnioskodawców. Ostateczną decyzję podejmuje urzędnik.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import config
import db
from routers import cases, intake, knowledge, response
from schemas import Health
from services import llm


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(
    title="Asystent UDIP — API",
    description="Backend obsługi wniosków o udostępnienie informacji publicznej (UM Bydgoszczy). "
    "API wspiera decyzje urzędnika i przygotowuje materiały, ale niczego samo nie wysyła na zewnątrz ani do wydziałów.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)


@app.get("/", response_model=Health, tags=["0. Zdrowie"])
def health():
    """Czy backend działa, w jakim trybie sieciowym (OFFLINE_MODE) i z jakim modelem."""
    return {
        "status": "ok",
        "offline_mode": config.OFFLINE_MODE,
        "model": llm.model_name(),
        "llm_enabled": llm.enabled(),
        "fts5": db.FTS_ENABLED,
    }


app.include_router(intake.router)
app.include_router(cases.router)
app.include_router(response.router)
app.include_router(knowledge.router)
