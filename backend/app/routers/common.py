"""Elementy wspólne routerów."""
from fastapi import UploadFile

import config
from errors import BadRequest, PayloadTooLarge

UPLOAD_ERRORS = {
    400: {"description": "Pusty plik, nieobsługiwany format albo uszkodzony dokument."},
    413: {"description": "Plik większy niż MAX_UPLOAD_MB."},
    422: {"description": "Brak warstwy tekstowej i brak możliwości wykonania OCR."},
}
LLM_ERRORS = {
    403: {"description": "OFFLINE_MODE=true — treść nie może zostać wysłana do Gemini."},
    502: {"description": "Gemini nie odpowiedział poprawnie, a zapas regułowy jest wyłączony."},
}


def read_upload(file: UploadFile) -> bytes:
    """Odczyt synchroniczny: endpointy są zwykłymi funkcjami, które FastAPI wykonuje w puli wątków,
    więc długi OCR i wywołania modelu nie blokują pętli zdarzeń."""
    data = file.file.read(config.MAX_UPLOAD_BYTES + 1)
    if len(data) > config.MAX_UPLOAD_BYTES:
        raise PayloadTooLarge(f"Plik przekracza {config.MAX_UPLOAD_MB} MB.")
    if not data:
        raise BadRequest("Plik jest pusty.")
    return data
