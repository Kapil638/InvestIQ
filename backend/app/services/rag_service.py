"""RAG service – retrieve similar past research reports from ChromaDB."""

from app.database.chroma_store import ChromaVectorStore
from app.schemas.storage import SimilarReportsResponse
from app.utils.exceptions import ConfigurationError


class RagService:
    """Semantic search over indexed research reports."""

    def __init__(self, vector_store: ChromaVectorStore | None) -> None:
        self._vector_store = vector_store

    @property
    def is_enabled(self) -> bool:
        return self._vector_store is not None

    async def search_similar(
        self,
        query: str,
        *,
        ticker: str | None = None,
        limit: int = 5,
    ) -> SimilarReportsResponse:
        if not self._vector_store:
            raise ConfigurationError(
                "ChromaDB is not enabled. Set CHROMA_ENABLED=true to use RAG search."
            )

        results = await self._vector_store.search_similar(
            query, ticker=ticker, limit=limit
        )
        return SimilarReportsResponse(query=query, ticker=ticker, results=results)

    async def get_context_for_ticker(self, ticker: str, limit: int = 3) -> str:
        """
        Build RAG context string from similar past reports for a ticker.

        Injected into ResearchContext as institutional memory for the research crew.
        """
        if not self._vector_store:
            return ""

        symbol = ticker.strip().upper()
        response = await self.search_similar(
            f"investment thesis risks valuation recommendation for {symbol}",
            ticker=symbol,
            limit=limit,
        )
        if not response.results:
            # Fallback: still try semantic neighbors without ticker filter
            response = await self.search_similar(
                f"comparable investment research for {symbol}",
                ticker=None,
                limit=limit,
            )
        if not response.results:
            return ""

        lines = [
            f"Semantic institutional memory related to {symbol} "
            "(use for continuity and peer patterns; do not invent unseen facts):"
        ]
        for match in response.results:
            ticker_tag = match.ticker or "UNKNOWN"
            rating = match.rating or "N/A"
            score_bit = f" similarity={match.relevance_score:.3f}"
            lines.append(f"- [{ticker_tag} | {rating}{score_bit}] {match.snippet}")
        return "\n".join(lines)

