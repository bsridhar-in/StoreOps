from storeops.core.events import (
    ActivityCreated,
    ActivityDeleted,
    ActivityUpdated,
    EventBus,
    ProgrammeCreated,
    ProgrammeMemberAdded,
)
from storeops.modules.reports import InMemoryMetricsRepository, ReportService


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
