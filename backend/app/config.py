"""Ustawienia backendu ze zmiennych środowiskowych oraz stałe tożsamości urzędu używane w pismach."""
import os
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "tak", "on"}


def _env_list(name: str, default: str) -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


BASE_DIR = Path(__file__).resolve().parent

DB_PATH = Path(os.getenv("DB_PATH", BASE_DIR / "data" / "udip.db"))
SEED_DEMO_DATA = _env_bool("SEED_DEMO_DATA", True)
SEED_FILE = Path(os.getenv("SEED_FILE", BASE_DIR / "seed" / "umb_demo.json"))

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
CORS_ORIGINS = _env_list("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")

# Model językowy: Google Gemini przez endpoint zgodny z OpenAI. Klucz jest wymagany do analizy wniosków i projektów pism.
LLM_BASE_URL = (os.getenv("LLM_BASE_URL") or "https://generativelanguage.googleapis.com/v1beta/openai").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL") or "gemini-2.5-flash"
LLM_API_KEY = (os.getenv("GEMINI_API_KEY") or os.getenv("LLM_API_KEY") or "").strip().strip('"')
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT", "90"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
LLM_DRAFT_MAX_TOKENS = int(os.getenv("LLM_DRAFT_MAX_TOKENS", "8192"))
# "none" wyłącza „myślenie” Gemini 2.5 Flash: odpowiedź jest szybsza, a JSON nie zostaje ucięty limitem tokenów.
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "none")
# true = treść wniosków nie może opuścić serwera, więc każde wywołanie Gemini kończy się błędem 403.
OFFLINE_MODE = _env_bool("OFFLINE_MODE", False)

OCR_LANG = os.getenv("OCR_LANG", "pol")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

CASE_NUMBER_PREFIX = os.getenv("CASE_NUMBER_PREFIX", "BKS.IV.1431")
# Rejestr UMB liczy termin jako datę wpływu + 14 dni (formuła =E+14), bez przesuwania na dzień roboczy.
# true = termin wypadający w dzień wolny przesuwa się na następny dzień roboczy (art. 57 § 4 KPA).
DEADLINE_SHIFT_TO_WORKING_DAY = _env_bool("DEADLINE_SHIFT_TO_WORKING_DAY", False)

PDF_FONT_PATH = Path(os.getenv("PDF_FONT_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
PDF_FONT_BOLD_PATH = Path(os.getenv("PDF_FONT_BOLD_PATH", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))

# Tożsamość urzędu w pismach, według wzorów pism Biura Komunikacji Społecznej UMB.
OFFICE_NAME = "Urząd Miasta Bydgoszczy"
OFFICE_NAME_GENITIVE = "Urzędu Miasta Bydgoszczy"
OFFICE_CITY = "Bydgoszcz"
OFFICE_LETTERHEAD = (
    "URZĄD MIASTA BYDGOSZCZY",
    "Biuro Komunikacji Społecznej",
    "85-102 Bydgoszcz, ul. Jezuicka 1",
    "tel. (52) 58 58 365, fax. (52) 58 58 623",
    "email: bks@um.bydgoszcz.pl, www.bydgoszcz.pl",
)
OFFICE_SIGNATURE = ("Biuro Komunikacji Społecznej", OFFICE_NAME)
