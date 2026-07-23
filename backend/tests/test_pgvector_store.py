"""Tests for PgVectorStore - replaces ChromaDB, stores embeddings in Supabase."""

from unittest.mock import MagicMock

import pytest

from app.database import pgvector_store
from app.database.pgvector_store import PgVectorStore


class FakeQuery:
    """Mimics supabase-py's chainable table query builder."""

    def __init__(self, table: "FakeTable", op: str) -> None:
        self.table = table
        self.op = op
        self.filters: list[tuple[str, str]] = []
        self.payload = None

    def eq(self, column: str, value: object) -> "FakeQuery":
        self.filters.append(("eq", column, value))
        return self

    def neq(self, column: str, value: object) -> "FakeQuery":
        self.filters.append(("neq", column, value))
        return self

    def execute(self) -> MagicMock:
        self.table.calls.append(self)
        return MagicMock(data=[])


class FakeTable:
    def __init__(self, client: "FakeClient", name: str) -> None:
        self.client = client
        self.name = name
        self.calls: list[FakeQuery] = []

    def insert(self, payload) -> FakeQuery:
        q = FakeQuery(self, "insert")
        q.payload = payload
        return q

    def delete(self) -> FakeQuery:
        return FakeQuery(self, "delete")


class FakeClient:
    def __init__(self) -> None:
        self.tables: dict[str, FakeTable] = {}
        self.rpc_calls: list[tuple[str, dict]] = []
        self.rpc_response_data: list[dict] = []

    def table(self, name: str) -> FakeTable:
        if name not in self.tables:
            self.tables[name] = FakeTable(self, name)
        return self.tables[name]

    def rpc(self, name: str, params: dict):
        self.rpc_calls.append((name, params))
        return MagicMock(execute=lambda: MagicMock(data=self.rpc_response_data))


@pytest.fixture(autouse=True)
def _fake_embeddings(monkeypatch: pytest.MonkeyPatch):
    """Avoid loading the real ONNX embedding model in unit tests."""
    monkeypatch.setattr(
        pgvector_store, "_embed", lambda texts: [[0.1, 0.2, 0.3] for _ in texts]
    )


def _store_with_fake_client() -> tuple[PgVectorStore, FakeClient]:
    store = PgVectorStore(url="https://example.supabase.co", key="anon-key")
    fake_client = FakeClient()
    store._client = fake_client
    return store, fake_client


@pytest.mark.asyncio
async def test_index_report_deletes_then_inserts_full_document() -> None:
    store, client = _store_with_fake_client()

    await store.index_report(
        report_id="r1",
        ticker="infy",
        document="full document text",
        rating="Buy",
        generated_at="2026-07-01T00:00:00Z",
    )

    table = client.tables[pgvector_store.TABLE_NAME]
    ops = [q.op for q in table.calls]
    assert ops == ["delete", "insert"]
    inserted = table.calls[1].payload
    assert inserted["ticker"] == "INFY"
    assert inserted["chunk_section"] == "full"
    assert inserted["embedding"] == [0.1, 0.2, 0.3]
    assert inserted["content"] == "full document text"


@pytest.mark.asyncio
async def test_index_report_chunks_inserts_all_chunks() -> None:
    store, client = _store_with_fake_client()

    await store.index_report_chunks(
        report_id="r1",
        ticker="INFY",
        chunks=[("analysis", "thesis text"), ("risks", "risk text")],
        rating="Hold",
        generated_at="2026-07-01T00:00:00Z",
    )

    table = client.tables[pgvector_store.TABLE_NAME]
    ops = [q.op for q in table.calls]
    assert ops == ["delete", "insert"]
    rows = table.calls[1].payload
    assert len(rows) == 2
    assert {r["chunk_section"] for r in rows} == {"analysis", "risks"}


@pytest.mark.asyncio
async def test_index_report_chunks_noop_for_empty_list() -> None:
    store, client = _store_with_fake_client()
    await store.index_report_chunks(
        report_id="r1", ticker="INFY", chunks=[], rating=None, generated_at="now"
    )
    assert pgvector_store.TABLE_NAME not in client.tables


@pytest.mark.asyncio
async def test_delete_report_deletes_by_report_id() -> None:
    store, client = _store_with_fake_client()
    await store.delete_report("r1")
    table = client.tables[pgvector_store.TABLE_NAME]
    assert table.calls[0].op == "delete"
    assert ("eq", "report_id", "r1") in table.calls[0].filters


@pytest.mark.asyncio
async def test_search_similar_calls_rpc_and_maps_results() -> None:
    store, client = _store_with_fake_client()
    client.rpc_response_data = [
        {
            "report_id": "r1",
            "ticker": "INFY",
            "rating": "Buy",
            "generated_at": "2026-07-01T00:00:00Z",
            "content": "matched snippet text",
            "similarity": 0.87,
        }
    ]

    results = await store.search_similar("investment thesis", ticker="infy", limit=3)

    assert len(client.rpc_calls) == 1
    rpc_name, params = client.rpc_calls[0]
    assert rpc_name == "match_report_embeddings"
    assert params["match_ticker"] == "INFY"
    assert params["match_count"] == 3
    assert params["query_embedding"] == [0.1, 0.2, 0.3]

    assert len(results) == 1
    match = results[0]
    assert match.report_id == "r1"
    assert match.ticker == "INFY"
    assert match.relevance_score == 0.87
    assert match.rating == "Buy"


@pytest.mark.asyncio
async def test_search_similar_returns_empty_list_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    store, client = _store_with_fake_client()

    def _boom(*_a, **_k):
        raise RuntimeError("connection failed")

    client.rpc = _boom  # type: ignore[method-assign]

    results = await store.search_similar("query")
    assert results == []


@pytest.mark.asyncio
async def test_index_report_swallows_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    """Indexing failures must not blow up report saving - RAG is best-effort."""
    store, client = _store_with_fake_client()

    def _boom(*_a, **_k):
        raise RuntimeError("db down")

    client.table = _boom  # type: ignore[method-assign]

    # Must not raise.
    await store.index_report(
        report_id="r1",
        ticker="INFY",
        document="doc",
        rating=None,
        generated_at="now",
    )


def test_embed_output_is_json_serializable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression test: chromadb's DefaultEmbeddingFunction returns numpy
    arrays of numpy.float32 scalars. list(vec) alone converts the array to a
    Python list but leaves numpy.float32 elements inside it, which the
    Supabase client's JSON serialization rejects with "Object of type
    float32 is not JSON serializable" - caught only by exercising the real
    embedding function, since every other test mocks _embed entirely (via
    the autouse _fake_embeddings fixture, undone here)."""
    import json

    monkeypatch.undo()  # reverse the autouse _fake_embeddings patch for this test only

    vectors = pgvector_store._embed(["a real sentence to embed"])
    assert len(vectors) == 1
    assert len(vectors[0]) == 384
    assert all(isinstance(x, float) for x in vectors[0])
    json.dumps(vectors[0])  # must not raise
