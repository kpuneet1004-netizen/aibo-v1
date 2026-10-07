import httpx
import pytest
import socket

from app.services.capabilities import fetch_url


def _patch_dns(monkeypatch, ip="93.184.216.34"):
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]
    )


def _fake_response(body: str, content_type: str, status_code: int = 200):
    class FakeResponse:
        def __init__(self):
            self.status_code = status_code
            self.headers = {"content-type": content_type}
            self.content = body.encode()
            self.text = body

        def raise_for_status(self):
            if not (200 <= self.status_code < 300):
                raise httpx.HTTPStatusError("bad status", request=None, response=self)

    return FakeResponse()


# 1. HTML -> clean visible text


def test_html_response_is_converted_to_clean_visible_text(monkeypatch):
    _patch_dns(monkeypatch)
    html = "<html><body><h1>Cafe Memoire</h1><p>Coffee and pastries, made fresh daily.</p></body></html>"
    monkeypatch.setattr(httpx.Client, "get", lambda self, *a, **k: _fake_response(html, "text/html; charset=utf-8"))

    result = fetch_url({"url": "https://example.com"})

    assert "<h1>" not in result["text"] and "<p>" not in result["text"]
    assert "Cafe Memoire" in result["text"]
    assert "Coffee and pastries, made fresh daily." in result["text"]


# 2. <script>/<style> content is excluded


def test_script_and_style_content_is_excluded(monkeypatch):
    _patch_dns(monkeypatch)
    html = (
        "<html><head><style>body{display:none}</style>"
        "<script>function trackVisitor(){ fetch('/evil'); }</script></head>"
        "<body><p>Visible page content.</p>"
        "<noscript>JavaScript is required.</noscript></body></html>"
    )
    monkeypatch.setattr(httpx.Client, "get", lambda self, *a, **k: _fake_response(html, "text/html"))

    result = fetch_url({"url": "https://example.com"})

    assert "display:none" not in result["text"]
    assert "trackVisitor" not in result["text"] and "/evil" not in result["text"]
    assert "JavaScript is required." not in result["text"]
    assert "Visible page content." in result["text"]


# 3. HTML entities are decoded


def test_html_entities_are_decoded(monkeypatch):
    _patch_dns(monkeypatch)
    html = "<html><body><p>Caf&eacute; serves coffee &amp; pastries, open 8am&ndash;6pm.</p></body></html>"
    monkeypatch.setattr(httpx.Client, "get", lambda self, *a, **k: _fake_response(html, "text/html"))

    result = fetch_url({"url": "https://example.com"})

    assert "Café serves coffee & pastries, open 8am\u20136pm." in result["text"]
    assert "&eacute;" not in result["text"] and "&amp;" not in result["text"] and "&ndash;" not in result["text"]


# 4. Non-HTML content is returned unchanged


def test_non_html_content_is_returned_unchanged(monkeypatch):
    _patch_dns(monkeypatch)
    body = '{"status": "ok", "note": "<not-actually-html>"}'
    monkeypatch.setattr(httpx.Client, "get", lambda self, *a, **k: _fake_response(body, "application/json"))

    result = fetch_url({"url": "https://example.com"})

    assert result["text"] == body


def test_plain_text_content_is_returned_unchanged(monkeypatch):
    _patch_dns(monkeypatch)
    body = "Just plain text, no markup at all."
    monkeypatch.setattr(httpx.Client, "get", lambda self, *a, **k: _fake_response(body, "text/plain"))

    result = fetch_url({"url": "https://example.com"})

    assert result["text"] == body


# 5. Existing SSRF protections still pass


def test_ssrf_protection_still_rejects_private_addresses(monkeypatch):
    with pytest.raises(ValueError, match="private or local"):
        fetch_url({"url": "http://127.0.0.1/"})


def test_ssrf_protection_still_rejects_hostnames_resolving_to_private_ips(monkeypatch):
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 443))]
    )
    with pytest.raises(ValueError, match="private or local"):
        fetch_url({"url": "https://internal.example.com"})


# 6. Existing fetch size limit still passes, and still applies to HTML


def test_size_limit_still_enforced_for_html_responses(monkeypatch):
    _patch_dns(monkeypatch)
    oversized_html = "<html><body>" + ("<p>filler</p>" * 100_000) + "</body></html>"
    assert len(oversized_html.encode()) > 1_000_000
    monkeypatch.setattr(httpx.Client, "get", lambda self, *a, **k: _fake_response(oversized_html, "text/html"))

    with pytest.raises(RuntimeError, match="exceeds 1 MB limit"):
        fetch_url({"url": "https://example.com"})


# Bonus: paragraph/heading boundaries are preserved, not collapsed


def test_block_boundaries_are_preserved_not_collapsed():
    from app.services.capabilities import _extract_visible_text

    html = "<html><body><h1>Title</h1><p>First paragraph.</p><p>Second paragraph.</p></body></html>"
    text = _extract_visible_text(html)
    lines = text.splitlines()

    assert "Title" in text and "First paragraph." in text and "Second paragraph." in text
    # Each block-level element must land on its own line, not be fused into
    # one run-on string with no boundary between them.
    assert "Title" in lines and "First paragraph." in lines and "Second paragraph." in lines


# Bonus: a page with no visible text at all falls back to raw source rather
# than returning an empty string (which would still pass verification but
# be useless to summarize_text and the dependency-injection fallback).


def test_html_with_no_visible_text_falls_back_to_raw_source(monkeypatch):
    _patch_dns(monkeypatch)
    only_script_html = "<html><body><script>var x = 1;</script></body></html>"
    monkeypatch.setattr(httpx.Client, "get", lambda self, *a, **k: _fake_response(only_script_html, "text/html"))

    result = fetch_url({"url": "https://example.com"})

    assert result["text"].strip() != ""
