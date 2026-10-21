import httpx
import pytest
from fastapi import FastAPI

from storeops.core.events import (
    ActivitiesBulkUpdated,
    ActivityCreated,
    ActivityDeleted,
    ActivityStatusChange,
    ActivityUpdated,
    EventBus,
    ProgrammeCreated,
    ProgrammeMemberAdded,
)
from storeops.modules.reports import InMemoryMetricsRepository, ReportService
from tests.headers import ALEX


def make_service() -> tuple[ReportService, EventBus]:
    bus = EventBus()
    service = ReportService(InMemoryMetricsRepository())
    service.register(bus)
    return service, bus


def test_unknown_store_has_zero_metrics() -> None:
    service, _ = make_service()

    metrics = service.get_store_metrics("store-xyz")

    assert metrics.activities_created == 0
    assert metrics.programmes_created == 0


def test_metrics_accumulate_from_events() -> None:
    service, bus = make_service()

    bus.publish(
        ActivityCreated(
            store_id="s1", activity_id="a1", title="t", created_by="u", assignee_id=None
        )
    )
    bus.publish(
        ActivityCreated(
            store_id="s1", activity_id="a2", title="t", created_by="u", assignee_id=None
        )
    )
    bus.publish(
        ActivityUpdated(
            store_id="s1",
            activity_id="a1",
            title="t",
            updated_by="u",
            changed_fields=("status",),
            status="done",
            assignee_id=None,
        )
    )
    bus.publish(
        ActivityUpdated(
            store_id="s1",
            activity_id="a2",
            title="t",
            updated_by="u",
            changed_fields=("priority",),
            status="done",
            assignee_id=None,
        )
    )
    bus.publish(ActivityDeleted(store_id="s1", activity_id="a2", deleted_by="u"))
    bus.publish(ProgrammeCreated(store_id="s1", programme_id="p1", name="P", created_by="u"))
    bus.publish(
        ProgrammeMemberAdded(
            store_id="s1", programme_id="p1", programme_name="P", staff_id="x", added_by="u"
        )
    )

    metrics = service.get_store_metrics("s1")

    assert metrics.activities_created == 2
    assert metrics.activities_completed == 1
    assert metrics.activities_deleted == 1
    assert metrics.programmes_created == 1
    assert metrics.programme_members_added == 1


def test_region_metrics_aggregate_stores() -> None:
    service, bus = make_service()
    for store_id in ("s1", "s1", "s2"):
        bus.publish(ProgrammeCreated(store_id=store_id, programme_id="p", name="P", created_by="u"))

    region = service.get_region_metrics("north", ["s1", "s2", "s3"])

    assert region.store_count == 3
    assert region.programmes_created == 3
    assert region.activities_created == 0


def _bulk_event(store_id: str, status: str, activity_ids: tuple[str, ...]) -> ActivitiesBulkUpdated:
    return ActivitiesBulkUpdated(
        store_id=store_id,
        updated_by="u",
        status=status,
        note=None,
        changes=tuple(
            ActivityStatusChange(activity_id=a, title="t", from_status="todo", assignee_id=None)
            for a in activity_ids
        ),
    )


def test_bulk_done_event_adds_one_completion_per_change() -> None:
    """AC-3.1: an ActivitiesBulkUpdated with 2 done changes adds 2 completions to that store."""
    service, bus = make_service()

    bus.publish(_bulk_event("store-001", "done", ("a1", "a2")))

    assert service.get_store_metrics("store-001").activities_completed == 2
    assert service.get_store_metrics("store-002").activities_completed == 0


def test_bulk_blocked_event_does_not_count_completions() -> None:
    """AC-3.2: a bulk update to blocked leaves completion metrics untouched."""
    service, bus = make_service()

    bus.publish(_bulk_event("store-001", "blocked", ("a1", "a2")))

    assert service.get_store_metrics("store-001").activities_completed == 0


async def _create(client: httpx.AsyncClient, title: str) -> str:
    response = await client.post("/api/activities", json={"title": title}, headers=ALEX)
    activity_id: str = response.json()["id"]
    return activity_id


@pytest.mark.anyio
async def test_bulk_done_over_http_counts_each_activity_once(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    """AC-3.1: bulk PATCH to done counts 2 completions (not 4) and only in store-001."""
    report_service: ReportService = app.state.report_service
    a_id = await _create(client, "Restock aisle 4")
    b_id = await _create(client, "Price check")
    assert report_service.get_store_metrics("store-001").activities_completed == 0

    response = await client.patch(
        "/api/activities/bulk-status", json={"ids": [a_id, b_id], "status": "done"}, headers=ALEX
    )

    assert response.status_code == 200
    assert report_service.get_store_metrics("store-001").activities_completed == 2
    assert report_service.get_store_metrics("store-002").activities_completed == 0


@pytest.mark.anyio
async def test_bulk_blocked_over_http_keeps_completions_and_created(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    """AC-3.2: bulk PATCH to blocked adds no completion and leaves activities_created at 2."""
    report_service: ReportService = app.state.report_service
    a_id = await _create(client, "Restock aisle 4")
    b_id = await _create(client, "Price check")

    response = await client.patch(
        "/api/activities/bulk-status",
        json={"ids": [a_id, b_id], "status": "blocked"},
        headers=ALEX,
    )

    assert response.status_code == 200
    metrics = report_service.get_store_metrics("store-001")
    assert metrics.activities_completed == 0
    assert metrics.activities_created == 2
