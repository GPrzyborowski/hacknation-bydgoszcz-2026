"""Klient Google Gemini przez endpoint zgodny z OpenAI Chat Completions."""
import json
import logging
import re
import time

import httpx

import config
from errors import BadGateway, Forbidden

log = logging.getLogger(__name__)

# 429 to limit zapytań na minutę, 5xx — chwilowe przeciążenie po stronie Google.
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
RETRY_DELAYS_SECONDS = (2.0, 5.0)
ERROR_BODY_EXCERPT = 300

_client: httpx.Client | None = None


class LLMDisabled(Exception):
    """Brak klucza API — wywołujący przechodzi na analizę regułową."""


class LLMForbidden(Forbidden):
    """OFFLINE_MODE=true: treść nie może opuścić serwera."""


class LLMError(BadGateway):
    """Gemini nie odpowiedział poprawnie."""


def enabled() -> bool:
    return bool(config.LLM_API_KEY and config.LLM_BASE_URL)


def model_name() -> str:
    return config.LLM_MODEL if enabled() else "heurystyka (brak klucza Gemini)"


def close() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None


def _http() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(timeout=config.LLM_TIMEOUT_SECONDS)
    return _client


def chat_json(system: str, user: str, max_tokens: int | None = None) -> dict:
    """Wysyła prompt i zwraca obiekt JSON z odpowiedzi modelu."""
    if not enabled():
        raise LLMDisabled()
    if config.OFFLINE_MODE:
        raise LLMForbidden("OFFLINE_MODE=true: wysyłka treści do Gemini jest zablokowana. Dane nie zostały wysłane.")

    payload = {
        "model": config.LLM_MODEL,
        "temperature": config.LLM_TEMPERATURE,
        "max_tokens": max_tokens or config.LLM_MAX_TOKENS,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    if config.LLM_REASONING_EFFORT:
        payload["reasoning_effort"] = config.LLM_REASONING_EFFORT
    response = _post_with_retries(payload)
    _raise_for_status(response)
    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LLMError("Nieoczekiwany format odpowiedzi Gemini.") from exc
    return parse_json_loose(content)


def _post_with_retries(payload: dict) -> httpx.Response:
    """Ponawia przy zerwanym połączeniu i odpowiedziach przejściowych (limit, przeciążenie)."""
    for delay in RETRY_DELAYS_SECONDS:
        try:
            response = _post(payload)
        except httpx.TransportError as exc:
            reason = exc.__class__.__name__
        else:
            if response.status_code not in RETRY_STATUSES:
                return response
            reason = f"HTTP {response.status_code}"
        log.info("Gemini chwilowo niedostępny (%s) — ponowienie za %.0f s", reason, delay)
        time.sleep(delay)
    try:
        return _post(payload)
    except httpx.TransportError as exc:
        raise LLMError(f"Brak połączenia z Gemini: {exc.__class__.__name__}") from exc


def _post(payload: dict) -> httpx.Response:
    """Przekroczenia czasu odpowiedzi nie ponawiamy — urzędnik czekałby dłużej niż limit przeglądarki."""
    try:
        return _http().post(
            f"{config.LLM_BASE_URL}/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {config.LLM_API_KEY}"},
        )
    except httpx.TimeoutException as exc:
        raise LLMError("Gemini nie odpowiedział w wyznaczonym czasie.") from exc


def _raise_for_status(response: httpx.Response) -> None:
    status = response.status_code
    if status < 400:
        return
    log.warning("Gemini zwrócił błąd HTTP %s", status)
    if status in (401, 403):
        hint = ""
        if config.LLM_API_KEY.startswith("AQ."):
            hint = " Klucz zaczyna się od „AQ.” — to nie jest klucz Google AI Studio; utwórz klucz „AIza…” na aistudio.google.com/apikey."
        raise LLMError(f"Gemini odrzucił klucz API (sprawdź GEMINI_API_KEY w pliku .env).{hint}")
    if status == 404:
        raise LLMError(f"Gemini nie zna modelu „{config.LLM_MODEL}” (sprawdź LLM_MODEL w .env, np. gemini-2.5-flash).")
    if status == 429:
        raise LLMError("Przekroczono limit zapytań Gemini — odczekaj chwilę i spróbuj ponownie.")
    raise LLMError(f"Gemini zwrócił błąd HTTP {status}: {response.text[:ERROR_BODY_EXCERPT]}")


def parse_json_loose(content: str) -> dict:
    """JSON z odpowiedzi modelu, także gdy jest opakowany w blok ```json lub otoczony tekstem."""
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (content or "").strip())
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        try:
            data = json.loads(text[start : end + 1]) if 0 <= start < end else None
        except json.JSONDecodeError:
            data = None
    if not isinstance(data, dict):
        raise LLMError("Gemini zwrócił odpowiedź, która nie jest poprawnym obiektem JSON.")
    return data
