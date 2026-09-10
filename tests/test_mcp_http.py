"""Tests d'intégration légers de l'application ASGI assemblée par `build_app`.

Vérifie uniquement la couche d'authentification bearer devant le endpoint
`/mcp` (voir README, vérification curl) : on ne teste pas le protocole MCP
Streamable HTTP lui-même (JSON-RPC, sessions...), seulement que le
middleware laisse ou non passer la requête vers l'application interne.
"""

from __future__ import annotations

import asyncio
import contextlib

import httpx

from ragifix_mcp.config import AppConfig
from ragifix_mcp.main import build_app


def _build_test_app(minimal_config_dict):
    config = AppConfig.model_validate(minimal_config_dict)
    return build_app(config)


@contextlib.asynccontextmanager
async def _lifespan(app):
    """Déclenche le cycle de vie ASGI (startup/shutdown) autour de `app`.

    `httpx.ASGITransport` n'envoie que des scopes "http" : sans ce cycle, le
    gestionnaire de session du SDK MCP (`StreamableHTTPSessionManager`) n'a
    pas démarré son `task group` et toute requête vers `/mcp` échoue avec
    "Task group is not initialized".
    """
    startup_complete = asyncio.Event()
    shutdown_requested = asyncio.Event()

    async def receive():
        if not startup_complete.is_set():
            return {"type": "lifespan.startup"}
        await shutdown_requested.wait()
        return {"type": "lifespan.shutdown"}

    async def send(message):
        if message["type"] == "lifespan.startup.complete":
            startup_complete.set()

    task = asyncio.create_task(app({"type": "lifespan"}, receive, send))
    await startup_complete.wait()
    try:
        yield
    finally:
        shutdown_requested.set()
        await task


def test_mcp_endpoint_without_token_returns_401(minimal_config_dict, mcp_token_env, ragifix_token_env):
    app = _build_test_app(minimal_config_dict)

    async def _call():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/mcp", json={})

    response = asyncio.run(_call())
    assert response.status_code == 401


def test_mcp_endpoint_with_wrong_token_returns_401(minimal_config_dict, mcp_token_env, ragifix_token_env):
    app = _build_test_app(minimal_config_dict)

    async def _call():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post("/mcp", json={}, headers={"Authorization": "Bearer wrong"})

    response = asyncio.run(_call())
    assert response.status_code == 401


def test_mcp_endpoint_with_valid_token_is_not_rejected_by_auth(
    minimal_config_dict, mcp_token_env, ragifix_token_env
):
    app = _build_test_app(minimal_config_dict)

    async def _call():
        async with _lifespan(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.post(
                    "/mcp",
                    json={},
                    headers={
                        "Authorization": "Bearer mcp-token",
                        "Accept": "application/json, text/event-stream",
                    },
                )

    response = asyncio.run(_call())
    # Le token est valide : la requête passe la couche d'authentification.
    # Le protocole MCP lui-même peut ensuite la rejeter pour d'autres raisons
    # (corps JSON-RPC invalide) — seul le contournement du 401 est vérifié ici.
    assert response.status_code != 401
