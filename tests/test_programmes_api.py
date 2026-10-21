from typing import Any

import httpx
import pytest

from tests.headers import ALEX, MANAGER, OTHER_STORE

pytestmark = pytest.mark.anyio


async def create_programme(
    client: httpx.AsyncClient, headers: dict[str, str] = MANAGER, **fields: object
) -> dict[str, Any]:
    body = {"name": "Holiday readiness", **fields}
    response = await client.post("/api/programmes", json=body, headers=headers)
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def test_list_is_scoped_to_authenticated_store(client: httpx.AsyncClient) -> None:
    mine = await create_programme(client)
    await create_programme(client, headers=OTHER_STORE, name="Other store programme")

    response = await client.get("/api/programmes", headers=ALEX)

    assert response.status_code == 200
    assert [p["id"] for p in response.json()] == [mine["id"]]


async def test_create_programme(client: httpx.AsyncClient) -> None:
    created = await create_programme(
        client, description="Q4 prep", start_date="2026-11-01", end_date="2026-12-31"
    )

    assert created["name"] == "Holiday readiness"
    assert created["start_date"] == "2026-11-01"
    assert created["member_ids"] == []
    assert created["created_by"] == "staff-mgr-1"


async def test_create_rejects_inverted_date_range(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/programmes",
        json={"name": "Bad", "start_date": "2026-12-31", "end_date": "2026-11-01"},
        headers=MANAGER,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_add_member(client: httpx.AsyncClient) -> None:
    programme = await create_programme(client)

    response = await client.post(
        f"/api/programmes/{programme['id']}/members",
        json={"staff_id": "staff-001"},
        headers=MANAGER,
    )

    assert response.status_code == 201
    assert response.json()["member_ids"] == ["staff-001"]


async def test_add_member_twice_conflicts(client: httpx.AsyncClient) -> None:
    programme = await create_programme(client)
    url = f"/api/programmes/{programme['id']}/members"
    await client.post(url, json={"staff_id": "staff-001"}, headers=MANAGER)

    response = await client.post(url, json={"staff_id": "staff-001"}, headers=MANAGER)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "ALREADY_A_MEMBER"


async def test_add_member_from_another_store_is_rejected(client: httpx.AsyncClient) -> None:
    programme = await create_programme(client)

    response = await client.post(
        f"/api/programmes/{programme['id']}/members",
        json={"staff_id": "staff-101"},
        headers=MANAGER,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNKNOWN_STAFF_MEMBER"


async def test_add_member_to_unknown_programme(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/programmes/prg_missing/members", json={"staff_id": "staff-001"}, headers=MANAGER
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROGRAMME_NOT_FOUND"
