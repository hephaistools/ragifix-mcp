"""Tests des outils MCP (`register_tools`).

Le SDK MCP réel n'est pas nécessaire pour ces tests : `register_tools`
n'utilise que `mcp.tool()` comme décorateur — le `FakeMcp` de `conftest.py`
capture les fonctions enregistrées, ce qui permet de tester le mapping
client → modèles Pydantic en isolation, sans protocole MCP ni réseau.
"""

from __future__ import annotations

import asyncio

import pytest

from ragifix_mcp.tools import (
    GetDocumentToolResult,
    HealthToolResult,
    ListDocumentsToolResult,
    ListSourcesToolResult,
    QueryToolResult,
    register_tools,
)


def test_register_tools_registers_all_five(fake_mcp, fake_ragifix_client):
    register_tools(fake_mcp, fake_ragifix_client())
    assert set(fake_mcp.tools) == {
        "rag_query",
        "rag_list_documents",
        "rag_get_document",
        "rag_health",
        "rag_list_sources",
    }


# -- rag_query --------------------------------------------------------------------

def test_rag_query_maps_results(fake_mcp, fake_ragifix_client):
    client = fake_ragifix_client(
        query_result={
            "results": [
                {
                    "chunk_id": "c1",
                    "doc_id": "d1",
                    "text": "texte",
                    "score": 0.9,
                    "metadata": {},
                    "origin": {"kind": "file", "uri": "file:///a.txt", "label": "a.txt"},
                }
            ]
        }
    )
    register_tools(fake_mcp, client)

    result = asyncio.run(fake_mcp.tools["rag_query"](query="question", top_k=3))

    assert isinstance(result, QueryToolResult)
    assert len(result.results) == 1
    assert result.results[0].chunk_id == "c1"
    assert result.results[0].origin.kind == "file"
    assert client.calls == [("query", "question", 3, None)]


def test_rag_query_default_top_k(fake_mcp, fake_ragifix_client):
    client = fake_ragifix_client()
    register_tools(fake_mcp, client)

    asyncio.run(fake_mcp.tools["rag_query"](query="q"))

    assert client.calls == [("query", "q", 5, None)]


def test_rag_query_without_origin(fake_mcp, fake_ragifix_client):
    client = fake_ragifix_client(
        query_result={
            "results": [
                {"chunk_id": "c1", "doc_id": "d1", "text": "t", "score": 0.5, "metadata": {}}
            ]
        }
    )
    register_tools(fake_mcp, client)

    result = asyncio.run(fake_mcp.tools["rag_query"](query="q"))
    assert result.results[0].origin is None


# -- rag_list_documents -------------------------------------------------------------

def test_rag_list_documents_maps_documents(fake_mcp, fake_ragifix_client):
    client = fake_ragifix_client(
        documents=[
            {
                "doc_id": "d1",
                "extension": "txt",
                "chunk_count": 2,
                "metadata": {},
                "updated_at": "2026-01-01T00:00:00Z",
            }
        ]
    )
    register_tools(fake_mcp, client)

    result = asyncio.run(fake_mcp.tools["rag_list_documents"]())

    assert isinstance(result, ListDocumentsToolResult)
    assert result.documents[0].doc_id == "d1"
    assert client.calls == [("list_documents", None)]


def test_rag_list_documents_passes_prefix(fake_mcp, fake_ragifix_client):
    client = fake_ragifix_client(documents=[])
    register_tools(fake_mcp, client)

    asyncio.run(fake_mcp.tools["rag_list_documents"](prefix="notes/"))

    assert client.calls == [("list_documents", "notes/")]


# -- rag_get_document ---------------------------------------------------------------

def test_rag_get_document_found(fake_mcp, fake_ragifix_client):
    client = fake_ragifix_client(
        get_document_result={
            "doc_id": "d1",
            "extension": "txt",
            "chunk_count": 1,
            "metadata": {},
            "updated_at": "2026-01-01T00:00:00Z",
        }
    )
    register_tools(fake_mcp, client)

    result = asyncio.run(fake_mcp.tools["rag_get_document"](doc_id="d1"))

    assert isinstance(result, GetDocumentToolResult)
    assert result.found is True
    assert result.document.doc_id == "d1"


def test_rag_get_document_not_found(fake_mcp, fake_ragifix_client):
    client = fake_ragifix_client(get_document_result=None)
    register_tools(fake_mcp, client)

    result = asyncio.run(fake_mcp.tools["rag_get_document"](doc_id="missing"))

    assert result.found is False
    assert result.doc_id == "missing"
    assert result.document is None


# -- rag_health -----------------------------------------------------------------------

def test_rag_health_reachable(fake_mcp, fake_ragifix_client):
    client = fake_ragifix_client(healthy=True)
    register_tools(fake_mcp, client)

    result = asyncio.run(fake_mcp.tools["rag_health"]())

    assert isinstance(result, HealthToolResult)
    assert result.ragifix_reachable is True


def test_rag_health_unreachable(fake_mcp, fake_ragifix_client):
    client = fake_ragifix_client(healthy=False)
    register_tools(fake_mcp, client)

    result = asyncio.run(fake_mcp.tools["rag_health"]())
    assert result.ragifix_reachable is False


# -- rag_list_sources ---------------------------------------------------------------

def test_rag_list_sources_maps_sources(fake_mcp, fake_ragifix_client):
    client = fake_ragifix_client(
        sources=[{"name": "s1", "description": "d", "enabled": True}]
    )
    register_tools(fake_mcp, client)

    result = asyncio.run(fake_mcp.tools["rag_list_sources"]())

    assert isinstance(result, ListSourcesToolResult)
    assert result.sources[0].name == "s1"
    assert result.sources[0].enabled is True


def test_rag_query_invalid_payload_raises_validation_error(fake_mcp, fake_ragifix_client):
    client = fake_ragifix_client(query_result={"results": [{"chunk_id": "c1"}]})  # champs requis manquants
    register_tools(fake_mcp, client)

    with pytest.raises(Exception):
        asyncio.run(fake_mcp.tools["rag_query"](query="q"))
