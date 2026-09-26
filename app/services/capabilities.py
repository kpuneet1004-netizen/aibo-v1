from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
import ipaddress
import socket
import httpx
from app.services.llm import llm_client

Handler = Callable[[dict[str, Any]], dict[str, Any]]
VerifierFn = Callable[[dict[str, Any]], None]

def _verify_text_response(result: dict[str, Any]) -> None:
    if not isinstance(result.get("text"), str) or not result["text"].strip():
        raise ValueError("respond/execute returned empty text")

def _verify_fetch_url(result: dict[str, Any]) -> None:
    if not isinstance(result.get("status_code"), int) or not 200 <= result["status_code"] < 300:
        raise ValueError("fetch_url did not return a successful HTTP status")
    if not isinstance(result.get("url"), str) or not result["url"].strip():
        raise ValueError("fetch_url returned no URL")
    if not isinstance(result.get("text"), str):
        raise ValueError("fetch_url returned no text")

def _verify_summarize_text(result: dict[str, Any]) -> None:
    summary = result.get("summary")
    source_chars = result.get("source_chars")
    if not isinstance(summary, str) or not summary.strip():
        raise ValueError("summarize_text returned an empty summary")
    if not isinstance(source_chars, int) or source_chars <= 0:
        raise ValueError("summarize_text returned invalid source_chars")
    if len(summary) > source_chars:
        raise ValueError("summarize_text summary exceeds source length")

@dataclass(frozen=True)
class CapabilityDefinition:
    name: str
    description: str
    risk: str
    requires_approval: bool
    handler: Handler
    verify: VerifierFn | None = None

class CapabilityRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, CapabilityDefinition] = {}
    def register(self, definition: CapabilityDefinition) -> None:
        self._definitions[definition.name] = definition
    def get(self, name: str) -> Handler | None:
        definition = self._definitions.get(name)
        return definition.handler if definition else None
    def definition(self, name: str) -> CapabilityDefinition | None:
        return self._definitions.get(name)
    def names(self) -> list[str]:
        return sorted(self._definitions)
    def contract(self) -> list[dict[str, Any]]:
        return [{"name": d.name, "description": d.description, "risk": d.risk, "requires_approval": d.requires_approval} for d in sorted(self._definitions.values(), key=lambda item: item.name)]

def respond_with_llm(payload: dict[str, Any]) -> dict[str, Any]:
    objective = str(payload.get("objective", "")).strip()
    if not objective:
        raise ValueError("objective is required")
    return llm_client.generate(objective)

def execute_with_llm(payload: dict[str, Any]) -> dict[str, Any]:
    return respond_with_llm(payload)

def summarize_text(payload: dict[str, Any]) -> dict[str, Any]:
    text = str(payload.get("text", "")).strip()
    if not text:
        dependencies = payload.get("_dependencies") or {}
        for dependency in dependencies.values():
            if isinstance(dependency, dict) and isinstance(dependency.get("text"), str) and dependency["text"].strip():
                text = dependency["text"].strip()
                break
    if not text:
        raise ValueError("text is required for summarization")
    summary = llm_client.summarize(text)
    if not isinstance(summary, str) or not summary.strip():
        raise RuntimeError("summarizer returned empty output")
    return {"summary": summary.strip(), "source_chars": len(text)}

def _reject_if_unsafe_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address, *, message: str) -> None:
    if address.is_private or address.is_loopback or address.is_link_local or address.is_multicast or address.is_reserved or address.is_unspecified:
        raise ValueError(message)

def _resolve_pinned_address(url: str) -> tuple[str, str, str, int]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("url must be an absolute http(s) URL")
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain", "metadata.google.internal"} or host.endswith(".local"):
        raise ValueError("private or local hosts are not allowed")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        _reject_if_unsafe_address(address, message="private or local IP addresses are not allowed")
        return parsed.scheme, host, str(address), port
    try:
        resolved = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("hostname could not be resolved") from exc
    if not resolved:
        raise ValueError("hostname did not resolve to an address")
    addresses = [ipaddress.ip_address(entry[4][0]) for entry in resolved]
    for candidate in addresses:
        _reject_if_unsafe_address(candidate, message="hostname resolves to a private or local IP address")
    return parsed.scheme, host, str(addresses[0]), port

def fetch_url(payload: dict[str, Any]) -> dict[str, Any]:
    url = str(payload.get("url", "")).strip()
    scheme, original_host, pinned_ip, port = _resolve_pinned_address(url)
    parsed = urlparse(url)
    netloc = f"[{pinned_ip}]:{port}" if ":" in pinned_ip else f"{pinned_ip}:{port}"
    pinned_url = f"{scheme}://{netloc}{parsed.path or '/'}"
    if parsed.query:
        pinned_url += f"?{parsed.query}"
    request_kwargs: dict[str, Any] = {"follow_redirects": False, "timeout": 15.0, "headers": {"User-Agent": "Aibo/1.0", "Host": original_host}}
    if scheme == "https":
        request_kwargs["extensions"] = {"sni_hostname": original_host}
    try:
        with httpx.Client() as client:
            response = client.get(pinned_url, **request_kwargs)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"URL fetch failed: {exc}") from exc
    if len(response.content) > 1_000_000:
        raise RuntimeError("URL response exceeds 1 MB limit")
    return {"url": url, "status_code": response.status_code, "content_type": response.headers.get("content-type", ""), "text": response.text}

capability_registry = CapabilityRegistry()
capability_registry.register(CapabilityDefinition("respond", "Generate a response using the configured LLM.", "low", False, respond_with_llm, _verify_text_response))
capability_registry.register(CapabilityDefinition("execute", "Compatibility capability for LLM execution.", "low", False, execute_with_llm, _verify_text_response))
capability_registry.register(CapabilityDefinition("fetch_url", "Fetch a public HTTP(S) URL and return its response.", "external_read", False, fetch_url, _verify_fetch_url))
capability_registry.register(CapabilityDefinition("summarize_text", "Summarize supplied or dependency-provided text.", "low", False, summarize_text, _verify_summarize_text))

for _definition in capability_registry._definitions.values():
    if _definition.verify is None:
        raise RuntimeError(f"Capability '{_definition.name}' has no verification contract")
