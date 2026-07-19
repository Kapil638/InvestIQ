from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_health_check_returns_ok() -> None:
    settings = Settings(app_env="test", debug=True)
    client = TestClient(create_app(settings=settings))

    response = client.get(f"{settings.api_prefix}/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app_name"] == "InvestIQ"
    assert data["environment"] == "test"
