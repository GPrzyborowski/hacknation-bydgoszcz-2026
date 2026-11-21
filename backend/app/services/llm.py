"""Klient Google Gemini (endpoint zgodny z OpenAI Chat Completions).

https://generativelanguage.googleapis.com/v1beta/openai/chat/completions, autoryzacja kluczem API
(GEMINI_API_KEY lub LLM_API_KEY). Bez klucza backend działa w trybie heurystycznym.
OFFLINE_MODE=true blokuje wysyłkę danych do zewnętrznego modelu (403) — zgodnie z dokumentacją API.
"""
import json
import re
import time

import httpx

import config


class LLMDisabled(Exception):
    """Brak klucza API — wywołujący przechodzi na heurystykę."""


class LLMForbidden(Exception):
    """OFFLINE_MODE=true — dane nie mogą opuścić serwera → 403."""


class LLMError(Exception):
    """Błąd komunikacji z Gemini lub niepoprawny JSON → heurystyka (LLM_FALLBACK_HEURISTIC) albo 502."""


def enabled() -> bool:
    return bool(config.LLM_API_KEY and config.LLM_BASE_URL)


def model_name() -> str:
    return config.LLM_MODEL if enabled() else "heurystyka (brak klucza Gemini)"


def check_offline_policy() -> None:
    if config.OFFLINE_MODE:
        raise LLMForbidden("OFFLINE_MODE=true: wysyłka treści do Gemini jest zablokowana. Dane nie zostały wysłane.")


# Gemini w darmowym planie zwraca 429 przy przekroczeniu limitu zapytań na minutę, a 503 przy przeciążeniu.
_RETRY_STATUS = {429, 500, 503}
_RETRY_DELAYS = (2.0, 5.0)


def chat_json(system: str, user: str, max_tokens: int = 4096) -> dict:
    """Wysyła prompt do Gemini i zwraca sparsowany obiekt JSON z odpowiedzi."""
    if not enabled():
        raise LLMDisabled()
    check_offline_policy()

    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {config.LLM_API_KEY}"}
    payload = {
        "model": config.LLM_MODEL,
        "temperature": config.LLM_TEMPERATURE,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    if config.LLM_REASONING_EFFORT:
        # Gemini 2.5 Flash: "none" wyłącza „myślenie”, które inaczej zjada limit max_tokens i ucina JSON.
        payload["reasoning_effort"] = config.LLM_REASONING_EFFORT

    url = f"{config.LLM_BASE_URL}/chat/completions"
    res = None
    for attempt in range(len(_RETRY_DELAYS) + 1):
        try:
            with httpx.Client(timeout=config.LLM_TIMEOUT) as client:
                res = client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            if attempt < len(_RETRY_DELAYS):
                time.sleep(_RETRY_DELAYS[attempt])
                continue
            raise LLMError(f"Brak połączenia z Gemini: {exc.__class__.__name__}") from exc
        if res.status_code in _RETRY_STATUS and attempt < len(_RETRY_DELAYS):
            time.sleep(_RETRY_DELAYS[attempt])
            continue
        break

    if res.status_code in (401, 403):
        hint = (
            " Klucz zaczyna się od „AQ.” — to nie jest klucz Google AI Studio; utwórz klucz „AIza…” na aistudio.google.com/apikey."
            if config.LLM_API_KEY.startswith("AQ.")
            else ""
        )
        raise LLMError(f"Gemini odrzucił klucz API (sprawdź GEMINI_API_KEY w pliku .env).{hint}")
    if res.status_code == 404:
        raise LLMError(f"Gemini nie zna modelu „{config.LLM_MODEL}” (sprawdź LLM_MODEL w .env, np. gemini-2.5-flash).")
    if res.status_code == 429:
        raise LLMError("Przekroczono limit zapytań Gemini — odczekaj chwilę i spróbuj ponownie.")
    if res.status_code >= 400:
        raise LLMError(f"Gemini zwrócił błąd HTTP {res.status_code}: {res.text[:300]}")
    try:
        content = res.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LLMError("Nieoczekiwany format odpowiedzi Gemini.") from exc
    return parse_json_loose(content)


def parse_json_loose(content: str) -> dict:
    text = (content or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise LLMError("Gemini zwrócił odpowiedź, która nie jest poprawnym JSON-em.")
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMError("Gemini zwrócił odpowiedź, która nie jest poprawnym JSON-em.") from exc
    if not isinstance(data, dict):
        raise LLMError("Gemini zwrócił JSON, który nie jest obiektem.")
    return data
