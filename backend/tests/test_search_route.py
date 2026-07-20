"""Tests for company search route."""

from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.api.dependencies import get_company_search_service
from app.core.config import Settings
from app.main import create_app
from app.providers.data_sources import NSE_SOURCE
from app.schemas.company_search import CompanySearchResponse, CompanySearchResult


def test_search_companies_route() -> None:
    mock_service = AsyncMock()
    mock_service.search.return_value = CompanySearchResponse(
        results=[
            CompanySearchResult(
                symbol="INFY",
                exchange="NSE",
                company_name="Infosys Limited",
                sector="Information Technology",
                source=NSE_SOURCE,
            )
        ],
        source=NSE_SOURCE,
    )

    app = create_app(settings=Settings(app_env="test", debug=True))
    app.dependency_overrides[get_company_search_service] = lambda: mock_service
    client = TestClient(app)

    response = client.get("/api/v1/search/companies", params={"q": "inf"})

    assert response.status_code == 200
    data = response.json()
    assert data["source"] == NSE_SOURCE
    assert data["results"][0]["symbol"] == "INFY"
    mock_service.search.assert_awaited_once_with("inf", limit=12)
