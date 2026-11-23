"""APIのテストで使う補助関数。"""

from fastapi.testclient import TestClient

DEFAULT_PASSWORD = "correct-horse-battery"


def log_in(client: TestClient, login_id: str, password: str = DEFAULT_PASSWORD) -> None:
    """事業者としてログインする。Cookie は、クライアントが保持する。"""
    response = client.post("/api/admin/login", json={"login_id": login_id, "password": password})
    assert response.status_code == 200, response.text
