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

# Tryb pracy bez internetu: LLM może być wywołany tylko pod adresem lokalnym / w sieci wewnętrznej.
OFFLINE_MODE = _bool("OFFLINE_MODE", False)

# Endpoint zgodny z OpenAI Chat Completions (Ollama: http://host:11434/v1, vLLM, LM Studio, ...).
# Pusty LLM_BASE_URL = tryb heurystyczny (bez modelu językowego) — przydatny do developmentu.
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:7b-instruct-q4_K_M")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "180"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))

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
