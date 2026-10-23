import httpx
import pytest
from fastapi import FastAPI

from storeops.modules.reports import ReportService
from tests.headers import ALEX, MANAGER, OTHER_STORE, SAM

pytestmark = pytest.mark.anyio


async def test_assignment_raises_alert_for_assignee_only(client: httpx.AsyncClient) -> None:
    await client.post(
        "/api/activities", json={"title": "Price check", "assignee_id": "staff-002"}, headers=ALEX
    )

    sam_alerts = (await client.get("/api/alerts", headers=SAM)).json()
    alex_alerts = (await client.get("/api/alerts", headers=ALEX)).json()

    assert [a["type"] for a in sam_alerts] == ["activity_assigned"]
    assert sam_alerts[0]["message"] == "You have been assigned 'Price check'"
    assert alex_alerts == []


async def test_status_change_alerts_assignee(client: httpx.AsyncClient) -> None:
    created = (
        await client.post(
            "/api/activities",
            json={"title": "Fix freezer", "assignee_id": "staff-002"},
            headers=ALEX,
        )
    ).json()
    await client.patch(f"/api/activities/{created['id']}", json={"status": "blocked"}, headers=ALEX)

    sam_alerts = (await client.get("/api/alerts", headers=SAM)).json()

    assert {a["type"] for a in sam_alerts} == {"activity_assigned", "activity_status_changed"}


async def test_programme_membership_raises_alert(client: httpx.AsyncClient) -> None:
    programme = (
        await client.post("/api/programmes", json={"name": "Loss prevention"}, headers=MANAGER)
    ).json()
    await client.post(
        f"/api/programmes/{programme['id']}/members",
        json={"staff_id": "staff-001"},
        headers=MANAGER,
    )

    alerts = (await client.get("/api/alerts", params={"unread_only": True}, headers=ALEX)).json()

    assert len(alerts) == 1
    assert alerts[0]["type"] == "programme_member_added"
    assert alerts[0]["source_id"] == programme["id"]
    assert alerts[0]["read"] is False


async def test_alerts_require_authentication(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/alerts")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"


OTHER_MANAGER = {"X-User-Id": "staff-mgr-2", "X-Store-Id": "store-002", "X-Role": "store_manager"}


async def _create(
    client: httpx.AsyncClient, headers: dict[str, str], title: str, assignee_id: str | None
) -> str:
    body: dict[str, str] = {"title": title}
    if assignee_id is not None:
        body["assignee_id"] = assignee_id
    response = await client.post("/api/activities", json=body, headers=headers)
    activity_id: str = response.json()["id"]
    return activity_id


def _status_alerts(alerts: list[dict[str, object]], source_id: str) -> list[dict[str, object]]:
    return [
        a for a in alerts if a["type"] == "activity_status_changed" and a["source_id"] == source_id
    ]


async def test_bulk_update_alerts_assignee_changed_by_someone_else(
    client: httpx.AsyncClient,
) -> None:
    """AC-3.3: SAM gets one status alert for A; ALEX gets none for his own activity B."""
    a_id = await _create(client, ALEX, "Restock aisle 4", "staff-002")
    b_id = await _create(client, ALEX, "Price check", "staff-001")

    response = await client.patch(
        "/api/activities/bulk-status", json={"ids": [a_id, b_id], "status": "done"}, headers=ALEX
    )

    assert response.status_code == 200
    sam_alerts = (await client.get("/api/alerts", headers=SAM)).json()
    alex_alerts = (await client.get("/api/alerts", headers=ALEX)).json()
    sam_status = _status_alerts(sam_alerts, a_id)
    assert len(sam_status) == 1
    assert sam_status[0]["message"] == "'Restock aisle 4' is now done"
    assert [a for a in sam_alerts if a["type"] == "activity_status_changed"] == sam_status
    assert _status_alerts(alex_alerts, b_id) == []


async def test_bulk_update_skips_unassigned_and_failed_items(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    """AC-3.4: unassigned A and other-store C (failed) raise no alerts and no completions."""
    a_id = await _create(client, ALEX, "Face up shelves", None)
    c_id = await _create(client, OTHER_STORE, "Clean freezer", "staff-101")

    response = await client.patch(
        "/api/activities/bulk-status", json={"ids": [a_id, c_id], "status": "blocked"}, headers=ALEX
    )

    assert response.status_code == 207
    assert [r["outcome"] for r in response.json()["results"]] == ["updated", "failed"]
    other_alerts = (await client.get("/api/alerts", headers=OTHER_STORE)).json()
    alex_alerts = (await client.get("/api/alerts", headers=ALEX)).json()
    sam_alerts = (await client.get("/api/alerts", headers=SAM)).json()
    assert [a for a in other_alerts if a["source_id"] == c_id] == []
    assert _status_alerts(alex_alerts, a_id) == []
    assert _status_alerts(sam_alerts, a_id) == []
    report_service: ReportService = app.state.report_service
    assert report_service.get_store_metrics("store-002").activities_completed == 0


async def test_bulk_update_alerts_stay_in_their_store(client: httpx.AsyncClient) -> None:
    """AC-3.5: store-002 assignee sees the bulk status alert; store-001 SAM does not."""
    c_id = await _create(client, OTHER_STORE, "Clean freezer", "staff-101")

    response = await client.patch(
        "/api/activities/bulk-status", json={"ids": [c_id], "status": "done"}, headers=OTHER_MANAGER
    )

    assert response.status_code == 200
    other_alerts = (await client.get("/api/alerts", headers=OTHER_STORE)).json()
    sam_alerts = (await client.get("/api/alerts", headers=SAM)).json()
    other_status = _status_alerts(other_alerts, c_id)
    assert len(other_status) == 1
    assert str(other_status[0]["message"]).endswith("is now done")
    assert [a for a in sam_alerts if a["source_id"] == c_id] == []
