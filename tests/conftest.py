"""Fixtures et utilitaires partagés pour la suite de tests de ragifix-mcp.

Aucun accès réseau réel : `RagifixAsyncClient` accepte un `transport`
injectable (`httpx.MockTransport`), et les outils MCP sont testés via un
`_FakeMcp` qui capture les fonctions enregistrées par `@mcp.tool()` sans
dépendre du protocole MCP complet.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

# Rend le package importable sans installation (lancement direct de pytest).
_SRC = Path(__file__).resolve().parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


@pytest.fixture
def minimal_config_dict():
    return {
        "server": {"auth_token_env": "RAGIFIX_MCP_TOKEN"},
        "ragifix": {"api_token_env": "RAGIFIX_API_TOKEN"},
    }


@pytest.fixture
def write_config(tmp_path):
    def _write(data: dict) -> Path:
        path = tmp_path / "config.yaml"
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        return path

    return _write


@pytest.fixture
def mcp_token_env(monkeypatch):
    monkeypatch.setenv("RAGIFIX_MCP_TOKEN", "mcp-token")
    return "mcp-token"


@pytest.fixture
def ragifix_token_env(monkeypatch):
    monkeypatch.setenv("RAGIFIX_API_TOKEN", "ragifix-token")
    return "ragifix-token"


class FakeMcp:
    """Fake du `MCPServer` : capture les fonctions décorées par `@mcp.tool()`
    sans dépendre du protocole MCP réel — `register_tools` n'utilise que
    cette unique méthode."""

    def __init__(self):
        self.tools: dict[str, callable] = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


@pytest.fixture
def fake_mcp():
    return FakeMcp()


class FakeRagifixAsyncClient:
    """Fake du client ragifix, pour tester le mapping des outils MCP sans
    passer par httpx."""

    def __init__(self, query_result=None, documents=None, get_document_result=None, healthy=True, sources=None):
        self.query_result = query_result or {"results": []}
        self.documents = documents if documents is not None else []
        self.get_document_result = get_document_result
        self.healthy = healthy
        self.sources = sources if sources is not None else []
        self.calls: list[tuple] = []

    async def query(self, query, top_k=5, filters=None):
        self.calls.append(("query", query, top_k, filters))
        return self.query_result

    async def list_documents(self, prefix=None):
        self.calls.append(("list_documents", prefix))
        return self.documents

    async def get_document(self, doc_id):
        self.calls.append(("get_document", doc_id))
        return self.get_document_result

    async def health(self):
        self.calls.append(("health",))
        return self.healthy

    async def get_sources(self):
        self.calls.append(("get_sources",))
        return self.sources


@pytest.fixture
def fake_ragifix_client():
    return FakeRagifixAsyncClient
