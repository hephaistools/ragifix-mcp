"""Client HTTP asynchrone vers ragifix, utilisé par les outils MCP."""

from __future__ import annotations

from urllib.parse import quote

import httpx


def _encode_doc_id(doc_id: str) -> str:
    return quote(doc_id, safe="/")


class RagifixAsyncClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = 60.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
            transport=transport,
        )

    async def query(self, query: str, top_k: int = 5, filters: dict | None = None) -> dict:
        response = await self._client.post("/query", json={"query": query, "top_k": top_k, "filters": filters})
        response.raise_for_status()
        return response.json()

    async def get_document(self, doc_id: str) -> dict | None:
        response = await self._client.get(f"/documents/{_encode_doc_id(doc_id)}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()

    async def list_documents(self) -> list[dict]:
        response = await self._client.get("/documents")
        response.raise_for_status()
        return response.json()["documents"]

    async def health(self) -> bool:
        try:
            response = await self._client.get("/health")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def get_sources(self) -> list[dict]:
        response = await self._client.get("/sources")
        response.raise_for_status()
        return response.json()["sources"]

    async def aclose(self) -> None:
        await self._client.aclose()
