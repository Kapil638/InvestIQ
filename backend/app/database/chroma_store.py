"""ChromaDB vector store for research report RAG."""

import asyncio
from typing import Any

from app.schemas.storage import SimilarReportMatch
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ChromaVectorStore:
    """Indexes report text for semantic similarity search."""

    def __init__(self, persist_directory: str, collection_name: str) -> None:
        self._persist_directory = persist_directory
        self._collection_name = collection_name
        self._client: Any = None
        self._collection: Any = None

    def _get_collection(self) -> Any:
        if self._collection is None:
            try:
                import chromadb
            except ImportError as exc:
                raise ImportError(
                    "chromadb is required for vector search. "
                    "Install with: pip install chromadb"
                ) from exc

            self._client = chromadb.PersistentClient(path=self._persist_directory)
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

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
            collection = self._get_collection()
            collection.upsert(
                ids=[report_id],
                documents=[document],
                metadatas=[
                    {
                        "ticker": ticker.upper(),
                        "rating": rating or "",
                        "generated_at": generated_at,
                    }
                ],
            )

        await asyncio.to_thread(_upsert)
        logger.info("Indexed report %s for ticker %s in ChromaDB", report_id, ticker)

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
            collection = self._get_collection()
            ids = [f"{report_id}:chunk:{idx}" for idx, _ in enumerate(chunks)]
            documents = [text for _, text in chunks]
            metadatas = [
                {
                    "report_id": report_id,
                    "ticker": ticker.upper(),
                    "section": section,
                    "rating": rating or "",
                    "generated_at": generated_at,
                }
                for section, _ in chunks
            ]
            collection.upsert(ids=ids, documents=documents, metadatas=metadatas)

        await asyncio.to_thread(_upsert_chunks)
        logger.info("Indexed %d chunks for report %s", len(chunks), report_id)

    async def delete_report(self, report_id: str) -> None:
        def _delete() -> None:
            collection = self._get_collection()
            collection.delete(ids=[report_id])
            try:
                existing = collection.get(where={"report_id": report_id})
                chunk_ids = existing.get("ids") or []
                if chunk_ids:
                    collection.delete(ids=chunk_ids)
            except Exception:
                pass

        await asyncio.to_thread(_delete)

    async def search_similar(
        self,
        query: str,
        *,
        ticker: str | None = None,
        limit: int = 5,
    ) -> list[SimilarReportMatch]:
        def _query() -> list[SimilarReportMatch]:
            collection = self._get_collection()
            where = {"ticker": ticker.upper()} if ticker else None
            results = collection.query(
                query_texts=[query],
                n_results=limit,
                where=where,
            )

            matches: list[SimilarReportMatch] = []
            ids = results.get("ids", [[]])[0]
            documents = results.get("documents", [[]])[0]
            distances = results.get("distances", [[]])[0]
            metadatas = results.get("metadatas", [[]])[0]

            for doc_id, doc, distance, meta in zip(ids, documents, distances, metadatas):
                relevance = max(0.0, 1.0 - float(distance))
                matches.append(
                    SimilarReportMatch(
                        report_id=doc_id,
                        ticker=(meta or {}).get("ticker", ""),
                        snippet=_truncate(doc, 300),
                        relevance_score=round(relevance, 4),
                        rating=(meta or {}).get("rating") or None,
                        generated_at=(meta or {}).get("generated_at"),
                    )
                )
            return matches

        return await asyncio.to_thread(_query)


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
