import httpx
import pytest

from tests.headers import ALEX, MANAGER, SAM

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
