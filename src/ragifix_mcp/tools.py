"""Outils MCP exposés par ragifix-mcp.

Chaque outil relaie simplement un appel vers l'API de ragifix — aucune
logique métier ici (pas de parsing, pas de chunking, pas d'embedding :
tout ça reste entièrement dans ragifix).

Les réponses utilisent des modèles Pydantic explicites plutôt qu'un `dict`
générique : le SDK MCP ne génère un schéma de sortie structuré
(`structured_content`) que pour des types de retour dont la forme est
connue (modèle Pydantic, dict paramétré, etc.) — un simple `-> dict` ne
produit qu'un bloc texte, sans structured_content exploitable par le
client.
"""

from __future__ import annotations

import logging

from mcp.server.mcpserver import MCPServer
from pydantic import BaseModel

from .ragifix_client import RagifixAsyncClient

logger = logging.getLogger(__name__)


class QueryResultItem(BaseModel):
    chunk_id: str
    doc_id: str
    text: str
    score: float
    metadata: dict


class QueryToolResult(BaseModel):
    results: list[QueryResultItem]


class DocumentInfo(BaseModel):
    doc_id: str
    chunk_count: int
    metadata: dict
    updated_at: str


class ListDocumentsToolResult(BaseModel):
    documents: list[DocumentInfo]


class GetDocumentToolResult(BaseModel):
    found: bool
    doc_id: str
    document: DocumentInfo | None = None


class HealthToolResult(BaseModel):
    ragifix_reachable: bool


class SourceInfo(BaseModel):
    name: str
    description: str
    enabled: bool


class ListSourcesToolResult(BaseModel):
    sources: list[SourceInfo]


def register_tools(mcp: MCPServer, client: RagifixAsyncClient) -> None:
    @mcp.tool()
    async def rag_query(query: str, top_k: int = 5) -> QueryToolResult:
        """Recherche les passages les plus pertinents dans la base documentaire ragifix pour une question donnée.

        Chaque résultat inclut `metadata`, dont la clé `uri` (lien ou chemin
        vers le document source). Cite-la pour indiquer à l'utilisateur où
        trouver le document d'origine.

        Args:
            query: La question ou le texte à rechercher.
            top_k: Nombre maximum de résultats à retourner (défaut: 5).
        """
        raw = await client.query(query, top_k=top_k)
        return QueryToolResult(results=[QueryResultItem(**r) for r in raw["results"]])

    @mcp.tool()
    async def rag_list_documents() -> ListDocumentsToolResult:
        """Liste les documents actuellement indexés dans ragifix."""
        documents = await client.list_documents()
        return ListDocumentsToolResult(documents=[DocumentInfo(**d) for d in documents])

    @mcp.tool()
    async def rag_get_document(doc_id: str) -> GetDocumentToolResult:
        """Retourne le détail d'un document indexé dans ragifix (nombre de chunks, métadonnées, date de mise à jour).

        `document.metadata` inclut notamment `uri` : le lien ou chemin vers
        le document source.

        Args:
            doc_id: Identifiant du document.
        """
        document = await client.get_document(doc_id)
        if document is None:
            return GetDocumentToolResult(found=False, doc_id=doc_id)
        return GetDocumentToolResult(found=True, doc_id=doc_id, document=DocumentInfo(**document))

    @mcp.tool()
    async def rag_health() -> HealthToolResult:
        """Vérifie que le service ragifix sous-jacent est joignable."""
        reachable = await client.health()
        return HealthToolResult(ragifix_reachable=reachable)

    @mcp.tool()
    async def rag_list_sources() -> ListSourcesToolResult:
        """Liste les sources de documents disponibles dans ragifix.

        Chaque source représente un ensemble de documents indexés (ex: un dossier local,
        un site SharePoint). Utilisez cette liste pour déterminer quelle source consulter
        en fonction de votre question.
        """
        sources = await client.get_sources()
        return ListSourcesToolResult(sources=[SourceInfo(**s) for s in sources])
