from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from tests.headers import ALEX, MANAGER, OTHER_STORE, SAM

pytestmark = pytest.mark.anyio


async def create_activity(
    client: httpx.AsyncClient, headers: dict[str, str] = ALEX, **fields: object
) -> dict[str, Any]:
    body = {"title": "Restock aisle 4", **fields}
    response = await client.post("/api/activities", json=body, headers=headers)
    assert response.status_code == 201, response.text
    data: dict[str, Any] = response.json()
    return data


async def test_requires_authentication(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/activities")

    assert response.status_code == 401
    assert response.json()["error"] == {
        "code": "UNAUTHORIZED",
        "message": "Missing X-User-Id or X-Store-Id header",
        "statusCode": 401,
    }


async def test_create_and_get_activity(client: httpx.AsyncClient) -> None:
    created = await create_activity(
        client, priority="high", category="inventory", assignee_id="staff-002"
    )

    assert created["status"] == "todo"
    assert created["priority"] == "high"
    assert created["created_by"] == "staff-001"
    assert created["store_id"] == "store-001"

    response = await client.get(f"/api/activities/{created['id']}", headers=ALEX)
    assert response.status_code == 200
    assert response.json() == created


async def test_create_rejects_invalid_body(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/activities", json={"title": ""}, headers=ALEX)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_create_rejects_assignee_from_another_store(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/activities", json={"title": "Face up", "assignee_id": "staff-101"}, headers=ALEX
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNKNOWN_ASSIGNEE"


async def test_create_rejects_unknown_programme(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/activities", json={"title": "Face up", "programme_id": "prg_missing"}, headers=ALEX
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNKNOWN_PROGRAMME"


async def test_list_filters_by_programme_and_status(client: httpx.AsyncClient) -> None:
    programme = (
        await client.post("/api/programmes", json={"name": "Summer reset"}, headers=MANAGER)
    ).json()
    in_programme = await create_activity(client, programme_id=programme["id"])
    standalone = await create_activity(client)
    await client.patch(
        f"/api/activities/{standalone['id']}", json={"status": "in_progress"}, headers=ALEX
    )
    await create_activity(client, headers=OTHER_STORE)

    all_items = (await client.get("/api/activities", headers=ALEX)).json()
    by_programme = (
        await client.get("/api/activities", params={"programme_id": programme["id"]}, headers=ALEX)
    ).json()
    by_status = (
        await client.get("/api/activities", params={"status": "in_progress"}, headers=ALEX)
    ).json()

    assert {a["id"] for a in all_items} == {in_programme["id"], standalone["id"]}
    assert [a["id"] for a in by_programme] == [in_programme["id"]]
    assert [a["id"] for a in by_status] == [standalone["id"]]


async def test_list_rejects_unknown_status_filter(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/activities", params={"status": "nope"}, headers=ALEX)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


async def test_activity_in_another_store_is_not_found(client: httpx.AsyncClient) -> None:
    created = await create_activity(client)

    response = await client.get(f"/api/activities/{created['id']}", headers=OTHER_STORE)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "ACTIVITY_NOT_FOUND"


async def test_patch_updates_allowed_fields(client: httpx.AsyncClient) -> None:
    created = await create_activity(client)

    response = await client.patch(
        f"/api/activities/{created['id']}",
        json={
            "status": "done",
            "priority": "urgent",
            "category": "compliance",
            "assignee_id": "staff-002",
        },
        headers=ALEX,
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["priority"], body["category"], body["assignee_id"]) == (
        "done",
        "urgent",
        "compliance",
        "staff-002",
    )
    assert body["title"] == created["title"]


async def test_patch_rejects_non_updatable_and_null_fields(client: httpx.AsyncClient) -> None:
    created = await create_activity(client)
    url = f"/api/activities/{created['id']}"

    extra = await client.patch(url, json={"title": "Renamed"}, headers=ALEX)
    null_status = await client.patch(url, json={"status": None}, headers=ALEX)

    assert extra.status_code == 422
    assert null_status.status_code == 422
    assert null_status.json()["error"]["code"] == "INVALID_FIELD"


async def test_patch_can_unassign(client: httpx.AsyncClient) -> None:
    created = await create_activity(client, assignee_id="staff-002")

    response = await client.patch(
        f"/api/activities/{created['id']}", json={"assignee_id": None}, headers=ALEX
    )

    assert response.status_code == 200
    assert response.json()["assignee_id"] is None


async def test_owner_can_delete(client: httpx.AsyncClient) -> None:
    created = await create_activity(client)

    response = await client.delete(f"/api/activities/{created['id']}", headers=ALEX)

    assert response.status_code == 204
    missing = await client.get(f"/api/activities/{created['id']}", headers=ALEX)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "ACTIVITY_NOT_FOUND"


async def test_store_manager_can_delete(client: httpx.AsyncClient) -> None:
    created = await create_activity(client)

    response = await client.delete(f"/api/activities/{created['id']}", headers=MANAGER)

    assert response.status_code == 204
    missing = await client.get(f"/api/activities/{created['id']}", headers=ALEX)
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "ACTIVITY_NOT_FOUND"


async def test_other_staff_cannot_delete(client: httpx.AsyncClient) -> None:
    created = await create_activity(client)

    response = await client.delete(f"/api/activities/{created['id']}", headers=SAM)

    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "ACTIVITY_DELETE_FORBIDDEN",
        "message": "Only the activity owner or a store manager can delete this activity",
        "statusCode": 403,
    }


async def test_clone_template_creates_four_planogram_activities(
    client: httpx.AsyncClient,
) -> None:
    """AC-2.1: cloning the default template persists 4 planogram activities."""
    programme = (
        await client.post("/api/programmes", json={"name": "Spring Refit"}, headers=MANAGER)
    ).json()

    response = await client.post(
        f"/api/programmes/{programme['id']}/templates", json={}, headers=ALEX
    )

    assert response.status_code == 201
    body = response.json()
    assert (body["programme_id"], body["template_key"]) == (
        programme["id"],
        "standard_planogram_reset",
    )
    assert len(body["activities"]) == 4
    for activity in body["activities"]:
        assert (activity["category"], activity["status"], activity["assignee_id"]) == (
            "planogram",
            "todo",
            None,
        )
        assert activity["department"] is not None
        assert activity["priority"] is not None

    listed = (
        await client.get("/api/activities", params={"programme_id": programme["id"]}, headers=ALEX)
    ).json()
    assert {a["id"] for a in listed} == {a["id"] for a in body["activities"]}


async def test_clone_template_into_other_store_programme_is_not_found(
    client: httpx.AsyncClient,
) -> None:
    """AC-2.2: a programme belonging to another store is reported as not found."""
    other_programme = (
        await client.post("/api/programmes", json={"name": "Other"}, headers=OTHER_STORE)
    ).json()

    response = await client.post(
        f"/api/programmes/{other_programme['id']}/templates", json={}, headers=ALEX
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROGRAMME_NOT_FOUND"
    remaining = (await client.get("/api/activities", headers=ALEX)).json()
    assert [a for a in remaining if a["category"] == "planogram"] == []


async def test_clone_template_requires_authentication(client: httpx.AsyncClient) -> None:
    """AC-2.3: missing auth headers on the clone route are rejected."""
    response = await client.post("/api/programmes/prg_anything/templates", json={})

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


async def test_clone_template_rejects_unknown_template_key(client: httpx.AsyncClient) -> None:
    """AC-2.4: an unknown template_key is rejected without creating activities."""
    programme = (await client.post("/api/programmes", json={"name": "P"}, headers=MANAGER)).json()

    response = await client.post(
        f"/api/programmes/{programme['id']}/templates",
        json={"template_key": "bogus"},
        headers=ALEX,
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "UNKNOWN_TEMPLATE_KEY"


async def test_clone_template_increments_report_metrics(
    client: httpx.AsyncClient, app: FastAPI
) -> None:
    """AC-2.5: each successful clone counts towards reports' templates_applied metric."""
    programme = (await client.post("/api/programmes", json={"name": "P"}, headers=MANAGER)).json()
    before = app.state.report_service.get_store_metrics("store-001")
    assert before.templates_applied == 0
    activities_created_before = before.activities_created

    first = await client.post(f"/api/programmes/{programme['id']}/templates", json={}, headers=ALEX)

    assert first.status_code == 201
    after_first = app.state.report_service.get_store_metrics("store-001")
    assert after_first.templates_applied == 1
    assert after_first.activities_created - activities_created_before == 4

    second = await client.post(
        f"/api/programmes/{programme['id']}/templates", json={}, headers=ALEX
    )

    assert second.status_code == 201
    after_second = app.state.report_service.get_store_metrics("store-001")
    assert after_second.templates_applied == 2
