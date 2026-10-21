from typing import Any

import httpx
import pytest

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
    remaining = await client.get("/api/activities", headers=ALEX)
    assert [a["id"] for a in remaining.json()] == []


async def test_other_staff_cannot_delete(client: httpx.AsyncClient) -> None:
    created = await create_activity(client)

    response = await client.delete(f"/api/activities/{created['id']}", headers=SAM)

    assert response.status_code == 403
    assert response.json()["error"] == {
        "code": "ACTIVITY_DELETE_FORBIDDEN",
        "message": "Only the activity owner or a store manager can delete this activity",
        "statusCode": 403,
    }


def assert_error(response: httpx.Response, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code


async def get_status(client: httpx.AsyncClient, activity_id: str, headers: dict[str, str]) -> str:
    response = await client.get(f"/api/activities/{activity_id}", headers=headers)
    assert response.status_code == 200, response.text
    status: str = response.json()["status"]
    return status


async def get_audit(
    client: httpx.AsyncClient, activity_id: str, headers: dict[str, str]
) -> list[dict[str, Any]]:
    response = await client.get(f"/api/activities/{activity_id}/audit", headers=headers)
    assert response.status_code == 200, response.text
    entries: list[dict[str, Any]] = response.json()
    return entries


async def test_bulk_status_all_succeed_returns_200_and_persists(
    client: httpx.AsyncClient,
) -> None:
    """AC-2.1: all ids updated -> 200, state persisted, one audit entry, single PATCH intact."""
    a = await create_activity(client)
    b = await create_activity(client, title="Price check endcap 2")

    response = await client.patch(
        "/api/activities/bulk-status",
        json={"ids": [a["id"], b["id"]], "status": "done", "note": "End of early shift"},
        headers=ALEX,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    assert body["updated_count"] == 2
    assert body["failed_count"] == 0
    assert [(r["id"], r["outcome"], r["code"]) for r in body["results"]] == [
        (a["id"], "updated", None),
        (b["id"], "updated", None),
    ]
    assert body["results"][0]["activity"]["id"] == a["id"]
    assert body["results"][0]["activity"]["status"] == "done"
    assert body["results"][1]["activity"]["status"] == "done"
    assert await get_status(client, a["id"], ALEX) == "done"
    assert await get_status(client, b["id"], ALEX) == "done"
    audit = await get_audit(client, a["id"], ALEX)
    assert len(audit) == 1
    entry = audit[0]
    assert {k: entry[k] for k in ("activity_id", "actor_id", "from_status", "to_status")} == {
        "activity_id": a["id"],
        "actor_id": "staff-001",
        "from_status": "todo",
        "to_status": "done",
    }
    assert entry["note"] == "End of early shift"
    assert entry["source"] == "bulk_status"
    assert entry["id"].startswith("aud")
    assert entry["created_at"]

    single = await client.patch(
        "/api/activities/act-missing", json={"status": "done"}, headers=ALEX
    )
    assert_error(single, 404, "ACTIVITY_NOT_FOUND")


async def test_bulk_status_partial_failure_returns_207(client: httpx.AsyncClient) -> None:
    """AC-2.2: mixed ids -> 207, successes saved, other store's activity untouched."""
    a = await create_activity(client)
    c = await create_activity(client, headers=OTHER_STORE, title="Other store task")

    response = await client.patch(
        "/api/activities/bulk-status",
        json={"ids": [a["id"], c["id"], "act-missing"], "status": "blocked"},
        headers=ALEX,
    )

    assert response.status_code == 207
    body = response.json()
    assert body["updated_count"] == 1
    assert body["failed_count"] == 2
    results = body["results"]
    assert (results[0]["id"], results[0]["outcome"], results[0]["code"]) == (
        a["id"],
        "updated",
        None,
    )
    assert results[0]["activity"]["status"] == "blocked"
    assert results[1] == {
        "id": c["id"],
        "outcome": "failed",
        "code": "ACTIVITY_NOT_FOUND",
        "activity": None,
    }
    assert results[2] == {
        "id": "act-missing",
        "outcome": "failed",
        "code": "ACTIVITY_NOT_FOUND",
        "activity": None,
    }
    assert await get_status(client, a["id"], ALEX) == "blocked"
    assert await get_status(client, c["id"], OTHER_STORE) == "todo"
    assert await get_audit(client, c["id"], OTHER_STORE) == []


async def test_bulk_status_every_id_failing_returns_207_and_changes_nothing(
    client: httpx.AsyncClient,
) -> None:
    """AC-2.3: all ids fail -> 207 with STATUS_UNCHANGED / ACTIVITY_NOT_FOUND, no audit."""
    a = await create_activity(client)
    blocked = await client.patch(
        f"/api/activities/{a['id']}", json={"status": "blocked"}, headers=ALEX
    )
    assert blocked.json()["status"] == "blocked"

    response = await client.patch(
        "/api/activities/bulk-status",
        json={"ids": [a["id"], "act-missing"], "status": "blocked"},
        headers=ALEX,
    )

    assert response.status_code == 207
    body = response.json()
    assert body["updated_count"] == 0
    assert body["failed_count"] == 2
    assert [(r["id"], r["outcome"], r["code"], r["activity"]) for r in body["results"]] == [
        (a["id"], "failed", "STATUS_UNCHANGED", None),
        ("act-missing", "failed", "ACTIVITY_NOT_FOUND", None),
    ]
    assert await get_audit(client, a["id"], ALEX) == []


async def test_bulk_status_and_audit_require_authentication(client: httpx.AsyncClient) -> None:
    """AC-2.4: both endpoints return 401 UNAUTHORIZED without headers."""
    bulk = await client.patch("/api/activities/bulk-status", json={"ids": ["x"], "status": "done"})
    audit = await client.get("/api/activities/x/audit")

    assert_error(bulk, 401, "UNAUTHORIZED")
    assert_error(audit, 401, "UNAUTHORIZED")


async def test_bulk_status_rejects_invalid_requests_with_exact_codes(
    client: httpx.AsyncClient,
) -> None:
    """AC-2.5: whole-request validation codes; nothing is changed or audited."""
    a = await create_activity(client)
    cases: list[tuple[dict[str, object], str]] = [
        ({"ids": [a["id"]], "status": "todo"}, "INVALID_BULK_STATUS"),
        ({"ids": [], "status": "done"}, "BULK_IDS_REQUIRED"),
        ({"ids": [f"act-{i}" for i in range(101)], "status": "done"}, "BULK_LIMIT_EXCEEDED"),
        ({"ids": [a["id"]], "status": "finished"}, "VALIDATION_ERROR"),
        ({"ids": [a["id"]], "status": "done", "priority": "high"}, "VALIDATION_ERROR"),
        ({"ids": [a["id"]], "status": "done", "note": "x" * 501}, "VALIDATION_ERROR"),
    ]

    codes = []
    for payload, _ in cases:
        response = await client.patch("/api/activities/bulk-status", json=payload, headers=ALEX)
        assert response.status_code == 422, response.text
        codes.append(response.json()["error"]["code"])

    assert codes == [code for _, code in cases]
    assert await get_status(client, a["id"], ALEX) == "todo"
    assert await get_audit(client, a["id"], ALEX) == []


async def test_audit_endpoint_is_store_scoped(client: httpx.AsyncClient) -> None:
    """AC-2.6: audit of another store's activity or unknown id is 404 ACTIVITY_NOT_FOUND."""
    c = await create_activity(client, headers=OTHER_STORE, title="Other store task")
    updated = await client.patch(
        "/api/activities/bulk-status",
        json={"ids": [c["id"]], "status": "done"},
        headers=OTHER_STORE,
    )
    assert updated.json()["updated_count"] == 1

    foreign = await client.get(f"/api/activities/{c['id']}/audit", headers=ALEX)
    missing = await client.get("/api/activities/act-missing/audit", headers=ALEX)

    assert_error(foreign, 404, "ACTIVITY_NOT_FOUND")
    assert_error(missing, 404, "ACTIVITY_NOT_FOUND")
    audit = await get_audit(client, c["id"], OTHER_STORE)
    assert [(e["actor_id"], e["to_status"]) for e in audit] == [("staff-101", "done")]
