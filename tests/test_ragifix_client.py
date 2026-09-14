"""Tests du client HTTP asynchrone vers ragifix.

Aucun accès réseau : `RagifixAsyncClient` accepte un `transport` injectable
(`httpx.MockTransport`).
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from ragifix_mcp.ragifix_client import RagifixAsyncClient, _encode_doc_id


# -- _encode_doc_id -----------------------------------------------------------

def test_encode_doc_id_preserves_slashes():
    assert _encode_doc_id("notes/a.txt") == "notes/a.txt"


def test_encode_doc_id_encodes_spaces():
    assert _encode_doc_id("doc with spaces.txt") == "doc%20with%20spaces.txt"


def _client_with_handler(handler) -> RagifixAsyncClient:
    transport = httpx.MockTransport(handler)
    return RagifixAsyncClient("http://test", "test-token", transport=transport)


# -- query ----------------------------------------------------------------------

def test_query_posts_expected_body_and_auth_header():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["method"] = request.method
        captured["path"] = request.url.path
        captured["auth"] = request.headers.get("authorization")
        captured["body"] = json.loads(request.read())
        return httpx.Response(200, json={"results": []})

    client = _client_with_handler(handler)
    result = asyncio.run(client.query("ma question", top_k=3))

    assert result == {"results": []}
    assert captured["method"] == "POST"
    assert captured["path"] == "/query"
    assert captured["auth"] == "Bearer test-token"
    assert captured["body"] == {"query": "ma question", "top_k": 3, "filters": None}


def test_query_raises_on_error_status():
    client = _client_with_handler(lambda r: httpx.Response(500))
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(client.query("x"))


# -- get_document -----------------------------------------------------------------

def test_get_document_found():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/documents/doc1"
        return httpx.Response(200, json={"doc_id": "doc1", "chunk_count": 1})

    client = _client_with_handler(handler)
    result = asyncio.run(client.get_document("doc1"))
    assert result == {"doc_id": "doc1", "chunk_count": 1}


def test_get_document_not_found_returns_none():
    client = _client_with_handler(lambda r: httpx.Response(404))
    assert asyncio.run(client.get_document("missing")) is None


def test_get_document_other_error_raises():
    client = _client_with_handler(lambda r: httpx.Response(500))
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(client.get_document("doc1"))


# -- list_documents -----------------------------------------------------------------

def test_list_documents_returns_documents():
    def handler(request: httpx.Request) -> httpx.Response:
        assert dict(request.url.params) == {}
        return httpx.Response(200, json={"documents": [{"doc_id": "a"}]})

    client = _client_with_handler(handler)
    assert asyncio.run(client.list_documents()) == [{"doc_id": "a"}]


def test_list_documents_sends_filters_as_query_params():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["params"] = request.url.params.multi_items()
        return httpx.Response(200, json={"documents": []})

    client = _client_with_handler(handler)
    asyncio.run(client.list_documents(filters={"source": ["a", "b"], "extension": "pdf"}))

    assert set(captured["params"]) == {("source", "a"), ("source", "b"), ("extension", "pdf")}


# -- health -----------------------------------------------------------------------

def test_health_true_on_200():
    client = _client_with_handler(lambda r: httpx.Response(200))
    assert asyncio.run(client.health()) is True


def test_health_false_on_non_200():
    client = _client_with_handler(lambda r: httpx.Response(503))
    assert asyncio.run(client.health()) is False


def test_health_false_on_connection_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connexion refusée", request=request)

    client = _client_with_handler(handler)
    assert asyncio.run(client.health()) is False


# -- get_sources -----------------------------------------------------------------

def test_get_sources_parses_response():
    client = _client_with_handler(lambda r: httpx.Response(200, json={"sources": [{"name": "s1"}]}))
    assert asyncio.run(client.get_sources()) == [{"name": "s1"}]


def test_get_sources_raises_on_error():
    client = _client_with_handler(lambda r: httpx.Response(500))
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(client.get_sources())


# -- aclose -----------------------------------------------------------------

def test_aclose_does_not_raise():
    client = _client_with_handler(lambda r: httpx.Response(200))
    asyncio.run(client.aclose())
