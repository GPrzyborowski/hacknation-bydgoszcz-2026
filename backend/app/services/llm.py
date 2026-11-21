"""Klient LLM zgodny z OpenAI Chat Completions (Ollama /v1, vLLM, LM Studio, llama.cpp server).

OFFLINE_MODE=true dopuszcza wyłącznie adresy lokalne / z sieci wewnętrznej — próba połączenia
z zewnętrznym endpointem kończy się 403, zanim jakiekolwiek dane opuszczą serwer.
"""
import ipaddress
import json
import re
import socket
from urllib.parse import urlparse

import httpx

import config


class LLMDisabled(Exception):
    """LLM nie skonfigurowany — wywołujący przechodzi na heurystykę."""


class LLMForbidden(Exception):
    """OFFLINE_MODE i endpoint spoza sieci lokalnej → 403."""


class LLMError(Exception):
    """Błąd komunikacji lub niepoprawny JSON → 502."""


def enabled() -> bool:
    return bool(config.LLM_BASE_URL)


def model_name() -> str:
    return config.LLM_MODEL if enabled() else "heurystyka (bez LLM)"


def _is_local_host(host: str) -> bool:
    if not host:
        return False
    if host in {"localhost", "host.docker.internal"} or "." not in host:
        # Nazwy jednoczłonowe (np. "ollama") to usługi w sieci Dockera / LAN.
        return True
    if host.endswith((".local", ".lan", ".internal", ".localdomain")):
        return True
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            addresses = [ipaddress.ip_address(info[4][0]) for info in socket.getaddrinfo(host, None)]
        except OSError:
            return False
    return all(a.is_private or a.is_loopback or a.is_link_local for a in addresses)


def check_offline_policy() -> None:
    if not config.OFFLINE_MODE or not enabled():
        return
    host = urlparse(config.LLM_BASE_URL).hostname or ""
    if not _is_local_host(host):
        raise LLMForbidden(
            f"OFFLINE_MODE=true: endpoint LLM „{host}” nie jest adresem lokalnym. Dane nie zostały wysłane."
        )


def chat_json(system: str, user: str, max_tokens: int = 2048) -> dict:
    """Wysyła prompt i zwraca sparsowany obiekt JSON z odpowiedzi modelu."""
    if not enabled():
        raise LLMDisabled()
    check_offline_policy()

    headers = {"Content-Type": "application/json"}
    if config.LLM_API_KEY:
        headers["Authorization"] = f"Bearer {config.LLM_API_KEY}"
    payload = {
        "model": config.LLM_MODEL,
        "temperature": config.LLM_TEMPERATURE,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    try:
        with httpx.Client(timeout=config.LLM_TIMEOUT) as client:
            res = client.post(f"{config.LLM_BASE_URL}/chat/completions", json=payload, headers=headers)
    except httpx.HTTPError as exc:
        raise LLMError(f"Brak połączenia z modelem językowym ({config.LLM_BASE_URL}): {exc.__class__.__name__}") from exc
    if res.status_code >= 400:
        raise LLMError(f"Model językowy zwrócił błąd HTTP {res.status_code}: {res.text[:300]}")
    try:
        content = res.json()["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise LLMError("Nieoczekiwany format odpowiedzi modelu językowego.") from exc
    return parse_json_loose(content)


def parse_json_loose(content: str) -> dict:
    text = (content or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            raise LLMError("Model zwrócił odpowiedź, która nie jest poprawnym JSON-em.")
        try:
            data = json.loads(text[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMError("Model zwrócił odpowiedź, która nie jest poprawnym JSON-em.") from exc
    if not isinstance(data, dict):
        raise LLMError("Model zwrócił JSON, który nie jest obiektem.")
    return data
