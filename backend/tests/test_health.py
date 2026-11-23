from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok() -> None:
    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_is_served_under_api() -> None:
    response = client.get("/api/openapi.json")

    assert response.status_code == 200
    assert "/api/health" in response.json()["paths"]
