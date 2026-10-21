from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

import storeops.modules.activities.service as activity_service_module
from storeops.core.auth import AuthContext, Role
from storeops.core.errors import NotFoundError, ValidationError
from storeops.core.events import (
    ActivitiesBulkUpdated,
    ActivityStatusChange,
    ActivityUpdated,
    EventBus,
)
from storeops.modules.activities import (
    ActivityService,
    ActivityStatus,
    InMemoryActivityAuditRepository,
    InMemoryActivityRepository,
)
from storeops.modules.activities.schemas import ActivityCreate, ActivityUpdate
from storeops.modules.programmes import InMemoryProgrammeRepository, ProgrammeService
from storeops.modules.staff import DEMO_STAFF, InMemoryStaffRepository, StaffService

ALEX_CTX = AuthContext(user_id="staff-001", store_id="store-001", role=Role.STAFF)
OTHER_CTX = AuthContext(user_id="staff-101", store_id="store-002", role=Role.STAFF)


@dataclass
class Harness:
    service: ActivityService
    bulk_events: list[ActivitiesBulkUpdated] = field(default_factory=list)
    updated_events: list[ActivityUpdated] = field(default_factory=list)


@pytest.fixture(autouse=True)
def ticking_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each call to the activities clock moves one second forward, so ordering is strict."""
    start = datetime(2026, 10, 21, 8, 0, tzinfo=UTC)
    ticks = iter(range(1_000_000))

    def fake_utcnow() -> datetime:
        return start + timedelta(seconds=next(ticks))

    monkeypatch.setattr(activity_service_module, "utcnow", fake_utcnow)


@pytest.fixture
def harness() -> Harness:
    bus = EventBus()
    staff = StaffService(InMemoryStaffRepository(DEMO_STAFF))
    programmes = ProgrammeService(InMemoryProgrammeRepository(), staff, bus)
    service = ActivityService(
        InMemoryActivityRepository(),
        staff,
        programmes,
        bus,
        audit_repo=InMemoryActivityAuditRepository(),
    )
    result = Harness(service=service)
    bus.subscribe(ActivitiesBulkUpdated, result.bulk_events.append)
    bus.subscribe(ActivityUpdated, result.updated_events.append)
    return result


def create(
    service: ActivityService,
    ctx: AuthContext = ALEX_CTX,
    title: str = "Restock aisle 4",
    assignee_id: str | None = None,
) -> str:
    return service.create_activity(ctx, ActivityCreate(title=title, assignee_id=assignee_id)).id


def test_bulk_update_marks_all_done_and_writes_one_audit_entry_each(harness: Harness) -> None:
    """AC-1.1: every activity is updated, results in order, one audit entry per activity."""
    service = harness.service
    a_id = create(service)
    b_id = create(service, title="Price check endcap 2")
    service.update_activity(ALEX_CTX, b_id, ActivityUpdate(status=ActivityStatus.IN_PROGRESS))
    a_before = service.get_activity(ALEX_CTX, a_id).updated_at
    b_before = service.get_activity(ALEX_CTX, b_id).updated_at

    result = service.bulk_update_status(
        ALEX_CTX, [a_id, b_id], ActivityStatus.DONE, note="End of shift"
    )

    assert result.updated_count == 2
    assert result.failed_count == 0
    assert [(r.id, r.outcome, r.code) for r in result.results] == [
        (a_id, "updated", None),
        (b_id, "updated", None),
    ]
    assert result.results[0].activity is not None
    assert result.results[0].activity.status == "done"
    a_after = service.get_activity(ALEX_CTX, a_id)
    b_after = service.get_activity(ALEX_CTX, b_id)
    assert (a_after.status, b_after.status) == ("done", "done")
    assert a_after.updated_at > a_before
    assert b_after.updated_at > b_before
    [a_entry] = service.list_audit_entries(ALEX_CTX, a_id)
    assert a_entry.actor_id == "staff-001"
    assert a_entry.from_status == "todo"
    assert a_entry.to_status == "done"
    assert a_entry.note == "End of shift"
    assert a_entry.source == "bulk_status"
    assert a_entry.store_id == "store-001"
    assert a_entry.activity_id == a_id
    [b_entry] = service.list_audit_entries(ALEX_CTX, b_id)
    assert b_entry.from_status == "in_progress"
    assert b_entry.to_status == "done"


def test_bulk_update_partial_failure_keeps_successes_and_isolates_other_store(
    harness: Harness,
) -> None:
    """AC-1.2: unknown and other-store ids fail with ACTIVITY_NOT_FOUND; the rest is saved."""
    service = harness.service
    a_id = create(service)
    c_id = create(service, ctx=OTHER_CTX, title="Other store task")

    result = service.bulk_update_status(
        ALEX_CTX, [a_id, c_id, "act-missing"], ActivityStatus.BLOCKED
    )

    assert [(r.id, r.outcome, r.code) for r in result.results] == [
        (a_id, "updated", None),
        (c_id, "failed", "ACTIVITY_NOT_FOUND"),
        ("act-missing", "failed", "ACTIVITY_NOT_FOUND"),
    ]
    assert result.updated_count == 1
    assert result.failed_count == 2
    assert [r.activity for r in result.results[1:]] == [None, None]
    assert service.get_activity(ALEX_CTX, a_id).status == "blocked"
    assert service.get_activity(OTHER_CTX, c_id).status == "todo"
    assert service.list_audit_entries(OTHER_CTX, c_id) == []


def test_bulk_update_reports_status_unchanged_without_rewriting(harness: Harness) -> None:
    """AC-1.3: an activity already in the target status fails STATUS_UNCHANGED, untouched."""
    service = harness.service
    a_id = create(service)
    service.update_activity(ALEX_CTX, a_id, ActivityUpdate(status=ActivityStatus.BLOCKED))
    before = service.get_activity(ALEX_CTX, a_id).updated_at

    result = service.bulk_update_status(ALEX_CTX, [a_id], ActivityStatus.BLOCKED)

    assert [(r.id, r.outcome, r.code, r.activity) for r in result.results] == [
        (a_id, "failed", "STATUS_UNCHANGED", None)
    ]
    assert service.get_activity(ALEX_CTX, a_id).updated_at == before
    assert service.list_audit_entries(ALEX_CTX, a_id) == []
    assert harness.bulk_events == []


@pytest.mark.parametrize("status", [ActivityStatus.TODO, ActivityStatus.IN_PROGRESS])
def test_bulk_update_rejects_status_other_than_done_or_blocked(
    harness: Harness, status: ActivityStatus
) -> None:
    """AC-1.4: todo / in_progress raise INVALID_BULK_STATUS and nothing changes."""
    service = harness.service
    a_id = create(service)

    with pytest.raises(ValidationError) as excinfo:
        service.bulk_update_status(ALEX_CTX, [a_id], status)

    assert excinfo.value.code == "INVALID_BULK_STATUS"
    assert excinfo.value.status_code == 422
    assert service.get_activity(ALEX_CTX, a_id).status == "todo"
    assert service.list_audit_entries(ALEX_CTX, a_id) == []
    assert harness.bulk_events == []


def test_bulk_update_rejects_more_than_100_distinct_ids(harness: Harness) -> None:
    """AC-1.5: 101 distinct ids raise BULK_LIMIT_EXCEEDED; no activity changes."""
    service = harness.service
    a_id = create(service)
    ids = [a_id] + [f"act-missing-{i}" for i in range(100)]

    with pytest.raises(ValidationError) as excinfo:
        service.bulk_update_status(ALEX_CTX, ids, ActivityStatus.DONE)

    assert excinfo.value.code == "BULK_LIMIT_EXCEEDED"
    assert excinfo.value.details == {"max": 100, "received": 101}
    assert service.get_activity(ALEX_CTX, a_id).status == "todo"
    assert harness.bulk_events == []


def test_bulk_update_rejects_empty_ids(harness: Harness) -> None:
    """AC-1.5: an empty id list raises BULK_IDS_REQUIRED; no event."""
    service = harness.service
    a_id = create(service)

    with pytest.raises(ValidationError) as excinfo:
        service.bulk_update_status(ALEX_CTX, [], ActivityStatus.DONE)

    assert excinfo.value.code == "BULK_IDS_REQUIRED"
    assert service.get_activity(ALEX_CTX, a_id).status == "todo"
    assert harness.bulk_events == []


def test_bulk_update_accepts_exactly_100_distinct_ids(harness: Harness) -> None:
    """AC-1.5: exactly 100 distinct ids (unknown allowed) returns 100 results."""
    service = harness.service
    a_id = create(service)
    ids = [a_id] + [f"act-missing-{i}" for i in range(99)]

    result = service.bulk_update_status(ALEX_CTX, ids, ActivityStatus.DONE)

    assert [r.id for r in result.results] == ids
    assert result.updated_count == 1
    assert result.failed_count == 99
    assert service.get_activity(ALEX_CTX, a_id).status == "done"


def test_bulk_update_collapses_duplicate_ids(harness: Harness) -> None:
    """AC-1.6: duplicates are processed once, in first-occurrence order."""
    service = harness.service
    a_id = create(service)
    b_id = create(service, title="Price check endcap 2")

    result = service.bulk_update_status(ALEX_CTX, [a_id, a_id, b_id, a_id], ActivityStatus.DONE)

    assert [(r.id, r.outcome) for r in result.results] == [(a_id, "updated"), (b_id, "updated")]
    assert result.updated_count == 2
    assert result.failed_count == 0
    assert len(service.list_audit_entries(ALEX_CTX, a_id)) == 1


def test_bulk_update_publishes_one_event_with_only_updated_activities(harness: Harness) -> None:
    """AC-1.7: one ActivitiesBulkUpdated listing exactly the changed activities."""
    service = harness.service
    a_id = create(service, assignee_id="staff-002")
    b_id = create(service, title="Price check endcap 2")
    c_id = create(service, ctx=OTHER_CTX, title="Other store task")
    harness.updated_events.clear()

    service.bulk_update_status(ALEX_CTX, [a_id, b_id, c_id], ActivityStatus.DONE, note="Handover")

    [event] = harness.bulk_events
    assert event.store_id == "store-001"
    assert event.updated_by == "staff-001"
    assert event.status == "done"
    assert event.note == "Handover"
    assert event.changes == (
        ActivityStatusChange(
            activity_id=a_id, title="Restock aisle 4", from_status="todo", assignee_id="staff-002"
        ),
        ActivityStatusChange(
            activity_id=b_id, title="Price check endcap 2", from_status="todo", assignee_id=None
        ),
    )
    assert harness.updated_events == []


def test_bulk_update_where_every_id_fails_publishes_no_event(harness: Harness) -> None:
    """AC-1.7: a bulk call with no successful update publishes no ActivitiesBulkUpdated."""
    service = harness.service
    c_id = create(service, ctx=OTHER_CTX, title="Other store task")

    result = service.bulk_update_status(ALEX_CTX, [c_id, "act-missing"], ActivityStatus.DONE)

    assert result.updated_count == 0
    assert result.failed_count == 2
    assert harness.bulk_events == []
    assert service.get_activity(OTHER_CTX, c_id).status == "todo"


def test_audit_trail_is_store_scoped(harness: Harness) -> None:
    """AC-1.8: another store's or an unknown activity's audit raises ACTIVITY_NOT_FOUND."""
    service = harness.service
    c_id = create(service, ctx=OTHER_CTX, title="Other store task")
    service.bulk_update_status(OTHER_CTX, [c_id], ActivityStatus.DONE)

    with pytest.raises(NotFoundError) as other_store:
        service.list_audit_entries(ALEX_CTX, c_id)
    with pytest.raises(NotFoundError) as missing:
        service.list_audit_entries(ALEX_CTX, "act-missing")

    assert other_store.value.code == "ACTIVITY_NOT_FOUND"
    assert missing.value.code == "ACTIVITY_NOT_FOUND"
    [entry] = service.list_audit_entries(OTHER_CTX, c_id)
    assert entry.actor_id == "staff-101"
    assert entry.activity_id == c_id


def test_audit_entries_are_listed_oldest_first(harness: Harness) -> None:
    """AC-1.1: repeated bulk updates append audit entries in chronological order."""
    service = harness.service
    a_id = create(service)

    service.bulk_update_status(ALEX_CTX, [a_id], ActivityStatus.BLOCKED)
    service.bulk_update_status(ALEX_CTX, [a_id], ActivityStatus.DONE, note="Unblocked")

    entries = service.list_audit_entries(ALEX_CTX, a_id)
    assert [(e.from_status, e.to_status, e.note) for e in entries] == [
        ("todo", "blocked", None),
        ("blocked", "done", "Unblocked"),
    ]
