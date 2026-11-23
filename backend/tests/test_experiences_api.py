import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.scenario import Catalog, build_catalog


@pytest.fixture
def catalog(session: Session) -> Catalog:
    return build_catalog(session)


def _titles(response_json: list[dict[str, object]]) -> list[str]:
    return [str(item["title"]) for item in response_json]


def test_list_returns_experiences_with_open_slots(client: TestClient, catalog: Catalog) -> None:
    response = client.get("/api/experiences")

    assert response.status_code == 200
    body = response.json()
    assert _titles(body) == ["海の体験", "夜の体験", "工芸の体験"]
    marine = body[0]
    assert marine["business_name"] == "海の事業者"
    assert marine["category"] == "marine"
    assert marine["confirmation_mode"] == "instant"
    assert [slot["id"] for slot in marine["slots"]] == [
        catalog.marine_today_afternoon.id,
        catalog.marine_tomorrow.id,
    ]
    assert marine["slots"][0]["remaining"] == 8
    assert marine["slots"][0]["is_full"] is False
    # 日時は、UTC（Z）で返す。日本時間の13:00は、UTCの04:00
    assert marine["slots"][0]["starts_at"] == "2026-11-24T04:00:00Z"
    assert "description" not in marine  # 一覧には、詳細の項目を含めない


def test_list_filters(client: TestClient, catalog: Catalog) -> None:
    assert _titles(client.get("/api/experiences", params={"kids_ok": "true"}).json()) == [
        "海の体験",
        "夜の体験",
    ]
    assert _titles(client.get("/api/experiences", params={"rain_ok": "true"}).json()) == [
        "工芸の体験"
    ]
    assert _titles(client.get("/api/experiences", params={"area": "那覇市"}).json()) == [
        "工芸の体験"
    ]
    assert _titles(client.get("/api/experiences", params={"category": "nature"}).json()) == [
        "夜の体験"
    ]
    assert _titles(client.get("/api/experiences", params={"max_minutes_from_naha": 60}).json()) == [
        "海の体験",
        "工芸の体験",
    ]
    assert _titles(client.get("/api/experiences", params={"date": "2026-11-25"}).json()) == [
        "海の体験",
        "工芸の体験",
    ]
    assert _titles(client.get("/api/experiences", params={"party_size": 5}).json()) == [
        "海の体験",
        "夜の体験",
    ]


@pytest.mark.parametrize(
    "params",
    [
        {"category": "unknown"},
        {"party_size": 0},
        {"party_size": 51},
        {"max_minutes_from_naha": -1},
        {"date": "not-a-date"},
    ],
)
def test_list_rejects_invalid_parameters_with_unified_error(
    client: TestClient, catalog: Catalog, params: dict[str, object]
) -> None:
    response = client.get("/api/experiences", params=params)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_detail_returns_description_and_all_open_slots(
    client: TestClient, catalog: Catalog
) -> None:
    response = client.get(f"/api/experiences/{catalog.craft.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "工芸の体験"
    assert body["description"]
    assert body["meeting_point"]
    slots = body["slots"]
    assert [slot["id"] for slot in slots] == [
        catalog.craft_today_full.id,
        catalog.craft_tomorrow.id,
    ]
    assert slots[0]["remaining"] == 0
    assert slots[0]["is_full"] is True  # 満席の便も、残席0で見える


def test_detail_of_missing_experience_is_404(client: TestClient) -> None:
    response = client.get("/api/experiences/99999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
