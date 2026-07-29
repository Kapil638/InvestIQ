from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.api.dependencies import get_report_storage_service
from app.core.config import Settings
from app.main import create_app


def test_database_status_connected() -> None:
    settings = Settings(app_env="test", debug=True)
    app = create_app(settings=settings)

    mock_storage = MagicMock()
    mock_storage.list_reports = AsyncMock(return_value=([], 0))
    app.dependency_overrides[get_report_storage_service] = lambda: mock_storage

    client = TestClient(app)
    response = client.get(f"{settings.api_prefix}/status/database")

    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is True
    assert data["latency_ms"] is not None


def test_database_status_reports_failure_not_500() -> None:
    settings = Settings(app_env="test", debug=True)
    app = create_app(settings=settings)

    mock_storage = MagicMock()
    mock_storage.list_reports = AsyncMock(side_effect=RuntimeError("connection refused"))
    app.dependency_overrides[get_report_storage_service] = lambda: mock_storage

    client = TestClient(app)
    response = client.get(f"{settings.api_prefix}/status/database")

    assert response.status_code == 200
    data = response.json()
    assert data["connected"] is False
    assert "connection refused" in data["message"]
