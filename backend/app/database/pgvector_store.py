"""Supabase/pgvector store for research report RAG - replaces ChromaDB.

ChromaDB persisted to local disk, which is ephemeral on Render's free tier;
CHROMA_ENABLED was set to false in production as a workaround, silently
disabling "institutional memory" entirely. This stores the same embeddings
in the Supabase Postgres database the app already depends on for durable
storage, removing the local-disk dependency instead of working around it.

Embeddings are generated with chromadb's bundled DefaultEmbeddingFunction
(ONNX-based all-MiniLM-L6-v2, 384 dims) purely as a local, free embedding
utility - no ChromaDB persistence/client involved, and no new dependency
since chromadb was already installed.
"""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import uuid4

from app.database.repositories.supabase_repository import _format_supabase_error
from app.schemas.storage import SimilarReportMatch
from app.utils.exceptions import ExternalServiceError
from app.utils.logging import get_logger

logger = get_logger(__name__)

TABLE_NAME = "report_embeddings"
_FULL_DOCUMENT_SECTION = "full"

_embedding_function: Any = None


def _get_embedding_function() -> Any:
    global _embedding_function
    if _embedding_function is None:
        from chromadb.utils import embedding_functions

        _embedding_function = embedding_functions.DefaultEmbeddingFunction()
    return _embedding_function


def _embed(texts: list[str]) -> list[list[float]]:
    ef = _get_embedding_function()
    # list(vec) alone leaves numpy.float32 scalars inside the list, which the
    # Supabase client's JSON serialization rejects - cast each element to a
    # native Python float explicitly.
    return [[float(x) for x in vec] for vec in ef(texts)]


class PgVectorStore:
    """Indexes report text for semantic similarity search via Supabase pgvector."""

    def __init__(self, url: str, key: str) -> None:
        self._url = url
        self._key = key
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from supabase import create_client
            except ImportError as exc:
                raise ImportError(
                    "supabase is required for pgvector storage. "
                    "Install with: pip install supabase"
                ) from exc
            self._client = create_client(self._url, self._key)
        return self._client

    async def index_report(
        self,
        *,
        report_id: str,
        ticker: str,
        document: str,
        rating: str | None,
        generated_at: str,
    ) -> None:
        def _upsert() -> None:
            client = self._get_client()
            client.table(TABLE_NAME).delete().eq("report_id", report_id).eq(
                "chunk_section", _FULL_DOCUMENT_SECTION
            ).execute()
            embedding = _embed([document])[0]
            client.table(TABLE_NAME).insert(
                {
                    "id": str(uuid4()),
                    "report_id": report_id,
                    "ticker": ticker.upper(),
                    "rating": rating or None,
                    "generated_at": generated_at,
                    "chunk_section": _FULL_DOCUMENT_SECTION,
                    "content": document,
                    "embedding": embedding,
                }
            ).execute()

        try:
            await asyncio.to_thread(_upsert)
            logger.info("Indexed report %s for ticker %s in pgvector", report_id, ticker)
        except Exception as exc:
            detail = _format_supabase_error(exc)
            logger.warning("pgvector indexing failed for %s: %s", report_id, detail)

    async def index_report_chunks(
        self,
        *,
        report_id: str,
        ticker: str,
        chunks: list[tuple[str, str]],
        rating: str | None,
        generated_at: str,
    ) -> None:
        if not chunks:
            return

        def _upsert_chunks() -> None:
            client = self._get_client()
            client.table(TABLE_NAME).delete().eq("report_id", report_id).neq(
                "chunk_section", _FULL_DOCUMENT_SECTION
            ).execute()
            embeddings = _embed([text for _, text in chunks])
            rows = [
                {
                    "id": str(uuid4()),
                    "report_id": report_id,
                    "ticker": ticker.upper(),
                    "rating": rating or None,
                    "generated_at": generated_at,
                    "chunk_section": section,
                    "content": text,
                    "embedding": embedding,
                }
                for (section, text), embedding in zip(chunks, embeddings)
            ]
            client.table(TABLE_NAME).insert(rows).execute()

        try:
            await asyncio.to_thread(_upsert_chunks)
            logger.info("Indexed %d chunks for report %s", len(chunks), report_id)
        except Exception as exc:
            detail = _format_supabase_error(exc)
            logger.warning("pgvector chunk indexing failed for %s: %s", report_id, detail)

    async def delete_report(self, report_id: str) -> None:
        def _delete() -> None:
            self._get_client().table(TABLE_NAME).delete().eq("report_id", report_id).execute()

        await asyncio.to_thread(_delete)

    async def search_similar(
        self,
        query: str,
        *,
        ticker: str | None = None,
        limit: int = 5,
    ) -> list[SimilarReportMatch]:
        def _query() -> list[SimilarReportMatch]:
            query_embedding = _embed([query])[0]
            response = (
                self._get_client()
                .rpc(
                    "match_report_embeddings",
                    {
                        "query_embedding": query_embedding,
                        "match_ticker": ticker.upper() if ticker else None,
                        "match_count": limit,
                    },
                )
                .execute()
            )
            rows = response.data or []

            matches: list[SimilarReportMatch] = []
            for row in rows:
                matches.append(
                    SimilarReportMatch(
                        report_id=row["report_id"],
                        ticker=row.get("ticker", ""),
                        snippet=_truncate(row["content"], 300),
                        relevance_score=round(max(0.0, float(row["similarity"])), 4),
                        rating=row.get("rating") or None,
                        generated_at=row.get("generated_at"),
                    )
                )
            return matches

        try:
            return await asyncio.to_thread(_query)
        except Exception as exc:
            detail = _format_supabase_error(exc)
            logger.warning("pgvector search failed: %s", detail)
            return []


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
