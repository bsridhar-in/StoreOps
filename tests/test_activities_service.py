from __future__ import annotations

import pytest

from storeops.core.auth import AuthContext, Role
from storeops.core.errors import NotFoundError, ValidationError
from storeops.core.events import ActivitiesTemplateCloned, EventBus
from storeops.modules.activities.models import ActivityCategory, ActivityStatus
from storeops.modules.activities.repository import InMemoryActivityRepository
from storeops.modules.activities.service import ActivityService
from storeops.modules.activities.templates import PLANOGRAM_TEMPLATES
from storeops.modules.programmes.repository import InMemoryProgrammeRepository
from storeops.modules.programmes.schemas import ProgrammeCreate
from storeops.modules.programmes.service import ProgrammeService
from storeops.modules.staff.repository import DEMO_STAFF, InMemoryStaffRepository
from storeops.modules.staff.service import StaffService

ALEX_CTX = AuthContext(user_id="staff-001", store_id="store-001", role=Role.STAFF)
MANAGER_STORE_002_CTX = AuthContext(
    user_id="staff-mgr-2", store_id="store-002", role=Role.STORE_MANAGER
)


def make_services() -> tuple[ActivityService, ProgrammeService, EventBus]:
    bus = EventBus()
    staff_service = StaffService(InMemoryStaffRepository(DEMO_STAFF))
    programme_service = ProgrammeService(InMemoryProgrammeRepository(), staff_service, bus)
    activity_service = ActivityService(
        InMemoryActivityRepository(), staff_service, programme_service, bus
    )
    return activity_service, programme_service, bus


def test_clone_creates_the_standard_planogram_task_set() -> None:
    """AC-1.1: cloning the standard template creates 4 activities matching the catalog, and
    publishes exactly one ActivitiesTemplateCloned event for the batch."""
    activity_service, programme_service, bus = make_services()
    programme = programme_service.create_programme(ALEX_CTX, ProgrammeCreate(name="Spring Refit"))
    received: list[ActivitiesTemplateCloned] = []
    bus.subscribe(ActivitiesTemplateCloned, received.append)
    definitions = PLANOGRAM_TEMPLATES["standard_planogram_reset"]

    created = activity_service.clone_template_into_programme(
        ALEX_CTX, programme.id, "standard_planogram_reset"
    )

    assert len(created) == 4
    for activity, definition in zip(created, definitions, strict=True):
        assert activity.category == ActivityCategory.PLANOGRAM
        assert activity.status == ActivityStatus.TODO
        assert activity.programme_id == programme.id
        assert activity.store_id == "store-001"
        assert activity.created_by == ALEX_CTX.user_id
        assert activity.assignee_id is None
        assert activity.department == definition.department
        assert activity.priority == definition.priority
        assert activity.title == definition.title

    for activity in created:
        stored = activity_service.get_activity(ALEX_CTX, activity.id)
        assert stored == activity

    assert len(received) == 1
    event = received[0]
    assert event.programme_id == programme.id
    assert event.template_key == "standard_planogram_reset"
    assert event.activity_ids == tuple(a.id for a in created)
    assert event.created_by == ALEX_CTX.user_id


def test_clone_rejects_unknown_programme_id() -> None:
    """AC-1.2: an unknown programme id raises PROGRAMME_NOT_FOUND and creates nothing."""
    activity_service, _, bus = make_services()
    received: list[ActivitiesTemplateCloned] = []
    bus.subscribe(ActivitiesTemplateCloned, received.append)

    with pytest.raises(NotFoundError) as exc_info:
        activity_service.clone_template_into_programme(
            ALEX_CTX, "prg-missing", "standard_planogram_reset"
        )
    assert exc_info.value.code == "PROGRAMME_NOT_FOUND"

    assert activity_service.list_activities(ALEX_CTX) == []
    assert received == []


def test_clone_rejects_programme_from_another_store() -> None:
    """AC-1.3: a programme that exists only in another store is reported as not found, never
    revealed to exist, and no activity leaks into either store."""
    activity_service, programme_service, bus = make_services()
    other_store_programme = programme_service.create_programme(
        MANAGER_STORE_002_CTX, ProgrammeCreate(name="Other Store Refit")
    )
    received: list[ActivitiesTemplateCloned] = []
    bus.subscribe(ActivitiesTemplateCloned, received.append)

    with pytest.raises(NotFoundError) as exc_info:
        activity_service.clone_template_into_programme(
            ALEX_CTX, other_store_programme.id, "standard_planogram_reset"
        )
    assert exc_info.value.code == "PROGRAMME_NOT_FOUND"

    assert activity_service.list_activities(ALEX_CTX) == []
    assert activity_service.list_activities(MANAGER_STORE_002_CTX) == []
    assert received == []


def test_clone_rejects_unknown_template_key() -> None:
    """AC-1.4: an unknown template_key raises UNKNOWN_TEMPLATE_KEY and creates nothing."""
    activity_service, programme_service, bus = make_services()
    programme = programme_service.create_programme(ALEX_CTX, ProgrammeCreate(name="Spring Refit"))
    received: list[ActivitiesTemplateCloned] = []
    bus.subscribe(ActivitiesTemplateCloned, received.append)

    with pytest.raises(ValidationError) as exc_info:
        activity_service.clone_template_into_programme(ALEX_CTX, programme.id, "does-not-exist")
    assert exc_info.value.code == "UNKNOWN_TEMPLATE_KEY"

    assert activity_service.list_activities(ALEX_CTX) == []
    assert received == []
