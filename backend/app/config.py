"""Konfiguracja backendu z zmiennych środowiskowych."""
import os
from pathlib import Path


def _bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "tak", "on"}


BASE_DIR = Path(__file__).resolve().parent

# Baza SQLite (z indeksem FTS5) — domyślnie w backend/app/data, katalog ignorowany przez git.
DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "data" / "udip.db"))

# OFFLINE_MODE=true blokuje wysyłkę treści do zewnętrznego modelu (Gemini) — odpowiedzi 403.
OFFLINE_MODE = _bool("OFFLINE_MODE", False)

# Model językowy: Google Gemini przez endpoint zgodny z OpenAI. Bez klucza API — tryb heurystyczny.
GEMINI_OPENAI_URL = "https://generativelanguage.googleapis.com/v1beta/openai"
LLM_BASE_URL = (os.getenv("LLM_BASE_URL") or GEMINI_OPENAI_URL).rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL") or "gemini-2.5-flash"
LLM_API_KEY = (os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY") or "").strip().strip('"')
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "90"))
# Gdy Gemini nie odpowie lub zwróci niepoprawny JSON: analiza heurystyczna z ostrzeżeniem zamiast błędu 502.
LLM_FALLBACK_HEURISTIC = _bool("LLM_FALLBACK_HEURISTIC", True)
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
# "none" wyłącza „myślenie” Gemini 2.5 Flash (szybciej, a JSON nie jest ucinany przez limit tokenów).
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "none")

# OCR (Tesseract) — język polski.
OCR_LANG = os.getenv("OCR_LANG", "pol")

# Prefiks znaku sprawy, gdy urzędnik nie poda numeru przy rejestracji.
CASE_NUMBER_PREFIX = os.getenv("CASE_NUMBER_PREFIX", "BKS.IV.1431")

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "20")) * 1024 * 1024

CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]

# Czcionka z polskimi znakami do eksportu PDF.
PDF_FONT_PATH = os.getenv("PDF_FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
PDF_FONT_BOLD_PATH = os.getenv("PDF_FONT_BOLD_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")

# Termin odpowiedzi: rejestr UMB („WNIOSKI O UDOSTĘPNIANIE INFORMACJI PUBLICZNEJ.xlsx”) liczy go jako
# datę wpływu + 14 dni (formuła =E+14), bez przesuwania na dzień roboczy. true = przesuwaj (art. 57 § 4 KPA).
DEADLINE_SHIFT_TO_WORKING_DAY = _bool("DEADLINE_SHIFT_TO_WORKING_DAY", False)

# Przy pierwszym starcie wczytaj 10 spraw testowych UMB (seed/umb_demo.json) do rejestru i archiwum.
SEED_DEMO_DATA = _bool("SEED_DEMO_DATA", True)
SEED_FILE = Path(os.getenv("SEED_FILE", BASE_DIR / "seed" / "umb_demo.json"))

# Nagłówek i podpis pism — wg wzorów odpowiedzi Biura Komunikacji Społecznej UMB (materiały wyzwania).
OFFICE_LETTERHEAD = [
    "URZĄD MIASTA BYDGOSZCZY",
    "Biuro Komunikacji Społecznej",
    "85-102 Bydgoszcz, ul. Jezuicka 1",
    "tel. (52) 58 58 365, fax. (52) 58 58 623",
    "email: bks@um.bydgoszcz.pl, www.bydgoszcz.pl",
]
OFFICE_SIGNATURE = ["Biuro Komunikacji Społecznej", "Urząd Miasta Bydgoszczy"]
OFFICE_CITY = os.getenv("OFFICE_CITY", "Bydgoszcz")
