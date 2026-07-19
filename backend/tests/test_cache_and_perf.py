"""Tests for TTL cache, LLM retry, and duplicate-call prevention."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import Settings
from app.llm.caller import call_llm_with_retry
from app.providers.data_sources import NSE_SOURCE
from app.schemas.company_search import CompanySearchResponse
from app.services.company_search_service import CompanySearchService
from app.services.research_crew_service import ResearchCrewService
from app.utils import ttl_cache


@pytest.fixture(autouse=True)
def clear_cache() -> None:
    ttl_cache.clear_all()
    yield
    ttl_cache.clear_all()


def test_ttl_cache_hit_when_enabled() -> None:
    settings = Settings(app_env="test", cache_enabled=True)
    with patch("app.utils.ttl_cache.get_settings", return_value=settings):
        ttl_cache.set("search", "inf:12", {"ok": True})
        assert ttl_cache.get("search", "inf:12") == {"ok": True}


def test_ttl_cache_miss_when_disabled() -> None:
    settings = Settings(app_env="test", cache_enabled=False)
    with patch("app.utils.ttl_cache.get_settings", return_value=settings):
        ttl_cache.set("search", "inf:12", {"ok": True})
        assert ttl_cache.get("search", "inf:12") is None


@pytest.mark.asyncio
async def test_company_search_uses_cache() -> None:
    settings = Settings(
        app_env="test",
        cache_enabled=True,
        tapetide_mcp_enabled=False,
        yfinance_enabled=False,
    )
    service = CompanySearchService(settings, tapetide_service=None, yahoo_provider=None)

    with (
        patch("app.utils.ttl_cache.get_settings", return_value=settings),
        patch.object(
            service,
            "_search_uncached",
            AsyncMock(return_value=CompanySearchResponse(results=[], source=NSE_SOURCE)),
        ) as mock_search,
    ):
        await service.search("inf")
        await service.search("inf")
        mock_search.assert_awaited_once()


def test_research_crew_has_no_collection_crew_method() -> None:
    assert not hasattr(ResearchCrewService, "_run_parallel_collection_crews")


def test_call_llm_retries_transient_429() -> None:
    llm = MagicMock()
    llm.call.side_effect = [Exception("429 rate limit"), "answer"]

    with patch("app.llm.caller.classify_llm_error") as classify:
        classify.side_effect = [
            MagicMock(status_code=429, message="rate", retryable=True),
            MagicMock(status_code=200, message="ok", retryable=False),
        ]
        with patch("app.llm.caller.time.sleep"):
            result = call_llm_with_retry(llm, "prompt", settings=Settings(app_env="test"))
    assert result == "answer"
    assert llm.call.call_count == 2


def test_call_llm_does_not_retry_auth_errors() -> None:
    llm = MagicMock()
    llm.call.side_effect = Exception("401 invalid api key")

    with patch(
        "app.llm.caller.classify_llm_error",
        return_value=MagicMock(status_code=401, message="auth", retryable=False),
    ):
        with pytest.raises(Exception, match="401"):
            call_llm_with_retry(llm, "prompt", settings=Settings(app_env="test"))
    assert llm.call.call_count == 1


def test_report_chat_does_not_use_research_crew() -> None:
    from app.services import report_chat_service

    source = open(report_chat_service.__file__, encoding="utf-8").read()
    assert "ResearchCrewService" not in source
