"""Tests du middleware ASGI d'authentification bearer."""

from __future__ import annotations

import asyncio

import pytest

from ragifix_mcp.auth import BearerAuthASGIMiddleware


def test_empty_token_raises():
    with pytest.raises(ValueError):
        BearerAuthASGIMiddleware(app=None, expected_token="")


class _RecordingApp:
    """App ASGI factice qui enregistre les scopes reçus et renvoie 200."""

    def __init__(self):
        self.calls: list[dict] = []

    async def __call__(self, scope, receive, send):
        self.calls.append(scope)
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})


async def _noop_receive():
    return {"type": "http.request"}


async def _run(middleware, scope):
    sent = []

    async def send(message):
        sent.append(message)

    await middleware(scope, _noop_receive, send)
    return sent


def _http_scope(headers: list[tuple[bytes, bytes]] | None = None) -> dict:
    return {"type": "http", "headers": headers or []}


def test_valid_bearer_forwards_to_inner_app():
    inner = _RecordingApp()
    mw = BearerAuthASGIMiddleware(inner, expected_token="secret")
    scope = _http_scope([(b"authorization", b"Bearer secret")])

    sent = asyncio.run(_run(mw, scope))

    assert len(inner.calls) == 1
    assert sent[0]["status"] == 200


def test_wrong_token_returns_401():
    inner = _RecordingApp()
    mw = BearerAuthASGIMiddleware(inner, expected_token="secret")
    scope = _http_scope([(b"authorization", b"Bearer wrong")])

    sent = asyncio.run(_run(mw, scope))

    assert inner.calls == []
    assert sent[0]["status"] == 401
    assert sent[1]["body"] == b'{"detail":"Token invalide ou manquant"}'


def test_missing_authorization_header_returns_401():
    inner = _RecordingApp()
    mw = BearerAuthASGIMiddleware(inner, expected_token="secret")
    scope = _http_scope([])

    sent = asyncio.run(_run(mw, scope))

    assert inner.calls == []
    assert sent[0]["status"] == 401


def test_missing_bearer_prefix_returns_401():
    inner = _RecordingApp()
    mw = BearerAuthASGIMiddleware(inner, expected_token="secret")
    scope = _http_scope([(b"authorization", b"secret")])

    sent = asyncio.run(_run(mw, scope))

    assert sent[0]["status"] == 401


def test_basic_auth_scheme_returns_401():
    inner = _RecordingApp()
    mw = BearerAuthASGIMiddleware(inner, expected_token="secret")
    scope = _http_scope([(b"authorization", b"Basic abc")])

    sent = asyncio.run(_run(mw, scope))

    assert sent[0]["status"] == 401


def test_bearer_with_extra_whitespace_is_stripped():
    inner = _RecordingApp()
    mw = BearerAuthASGIMiddleware(inner, expected_token="secret")
    scope = _http_scope([(b"authorization", b"Bearer   secret  ")])

    sent = asyncio.run(_run(mw, scope))

    assert len(inner.calls) == 1
    assert sent[0]["status"] == 200


def test_non_http_scope_passes_through_without_auth():
    inner = _RecordingApp()
    mw = BearerAuthASGIMiddleware(inner, expected_token="secret")
    scope = {"type": "lifespan"}

    asyncio.run(_run(mw, scope))

    assert len(inner.calls) == 1
