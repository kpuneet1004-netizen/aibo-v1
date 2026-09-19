from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse
import ipaddress
import httpx
from app.services.llm import llm_client

Handler = Callable[[dict[str, Any]], dict[str, Any]]

class CapabilityRegistry:
    def __init__(self) -> None:
        self._handlers: dict[str, Handler] = {}

    def register(self, name: str, handler: Handler) -> None:
        self._handlers[name] = handler

    def get(self, name: str) -> Handler | None:
        return self._handlers.get(name)

    def names(self) -> list[str]:
        return sorted(self._handlers)

def respond_with_llm(payload: dict[str, Any]) -> dict[str, Any]:
    objective = str(payload.get("objective", "")).strip()
    if not objective:
        raise ValueError("objective is required")
    return llm_client.generate(objective)

def execute_with_llm(payload: dict[str, Any]) -> dict[str, Any]:
    return respond_with_llm(payload)

def _validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("url must be an absolute http(s) URL")
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain", "metadata.google.internal"} or host.endswith(".local"):
        raise ValueError("private or local hosts are not allowed")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return
    if address.is_private or address.is_loopback or address.is_link_local or address.is_multicast or address.is_reserved or address.is_unspecified:
        raise ValueError("private or local IP addresses are not allowed")

def fetch_url(payload: dict[str, Any]) -> dict[str, Any]:
    url = str(payload.get("url", "")).strip()
    _validate_public_url(url)
    try:
        response = httpx.get(url, follow_redirects=False, timeout=15.0, headers={"User-Agent": "Aibo/1.0"})
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"URL fetch failed: {exc}") from exc
    if len(response.content) > 1_000_000:
        raise RuntimeError("URL response exceeds 1 MB limit")
    return {"url": str(response.url), "status_code": response.status_code, "content_type": response.headers.get("content-type", ""), "text": response.text}

capability_registry = CapabilityRegistry()
capability_registry.register("respond", respond_with_llm)
capability_registry.register("execute", execute_with_llm)
capability_registry.register("fetch_url", fetch_url)
