from __future__ import annotations

from dataclasses import replace

from storeops.core.auth import AuthContext
from storeops.core.clock import utcnow
from storeops.core.errors import ForbiddenError, NotFoundError, ValidationError
from storeops.core.events import (
    ActivitiesTemplateCloned,
    ActivityCreated,
    ActivityDeleted,
    ActivityUpdated,
    EventBus,
)
from storeops.core.ids import new_id
from storeops.modules.activities.models import Activity, ActivityCategory, ActivityStatus
from storeops.modules.activities.repository import ActivityRepository
from storeops.modules.activities.schemas import ActivityCreate, ActivityUpdate
from storeops.modules.activities.templates import PLANOGRAM_TEMPLATES
from storeops.modules.programmes import ProgrammeReader
from storeops.modules.staff import StaffReader

_NON_NULLABLE_FIELDS = frozenset({"status", "priority", "category"})


class ActivityService:
    def __init__(
        self,
        repo: ActivityRepository,
        staff: StaffReader,
        programmes: ProgrammeReader,
        bus: EventBus,
    ) -> None:
        self._repo = repo
        self._staff = staff
        self._programmes = programmes
        self._bus = bus

    def list_activities(
        self,
        ctx: AuthContext,
        *,
        programme_id: str | None = None,
        status: ActivityStatus | None = None,
    ) -> list[Activity]:
        return self._repo.list_by_store(ctx.store_id, programme_id=programme_id, status=status)

    def get_activity(self, ctx: AuthContext, activity_id: str) -> Activity:
        activity = self._repo.get(activity_id)
        if activity is None or activity.store_id != ctx.store_id:
            raise NotFoundError(f"Activity '{activity_id}' not found", code="ACTIVITY_NOT_FOUND")
        return activity

    def create_activity(self, ctx: AuthContext, data: ActivityCreate) -> Activity:
        if data.programme_id is not None and not self._programmes.exists_in_store(
            data.programme_id, ctx.store_id
        ):
            raise ValidationError(
                f"Programme '{data.programme_id}' does not exist in this store",
                code="UNKNOWN_PROGRAMME",
            )
        self._ensure_assignable(ctx, data.assignee_id)

        now = utcnow()
        activity = Activity(
            id=new_id("act"),
            store_id=ctx.store_id,
            title=data.title,
            description=data.description,
            status=ActivityStatus.TODO,
            priority=data.priority,
            category=data.category,
            programme_id=data.programme_id,
            assignee_id=data.assignee_id,
            created_by=ctx.user_id,
            created_at=now,
            updated_at=now,
        )
        self._repo.add(activity)
        self._bus.publish(
            ActivityCreated(
                store_id=ctx.store_id,
                activity_id=activity.id,
                title=activity.title,
                created_by=ctx.user_id,
                assignee_id=activity.assignee_id,
            )
        )
        return activity

    def update_activity(self, ctx: AuthContext, activity_id: str, data: ActivityUpdate) -> Activity:
        activity = self.get_activity(ctx, activity_id)
        changes = data.model_dump(exclude_unset=True)
        if not changes:
            return activity

        for field_name in sorted(_NON_NULLABLE_FIELDS & changes.keys()):
            if changes[field_name] is None:
                raise ValidationError(f"'{field_name}' cannot be null", code="INVALID_FIELD")
        if "assignee_id" in changes:
            self._ensure_assignable(ctx, changes["assignee_id"])

        updated = replace(activity, **changes, updated_at=utcnow())
        self._repo.update(updated)
        self._bus.publish(
            ActivityUpdated(
                store_id=ctx.store_id,
                activity_id=updated.id,
                title=updated.title,
                updated_by=ctx.user_id,
                changed_fields=tuple(sorted(changes)),
                status=updated.status.value,
                assignee_id=updated.assignee_id,
            )
        )
        return updated

    def delete_activity(self, ctx: AuthContext, activity_id: str) -> None:
        activity = self.get_activity(ctx, activity_id)
        if activity.created_by != ctx.user_id and not ctx.is_store_manager:
            raise ForbiddenError(
                "Only the activity owner or a store manager can delete this activity",
                code="ACTIVITY_DELETE_FORBIDDEN",
            )
        self._repo.delete(activity.id)
        self._bus.publish(
            ActivityDeleted(store_id=ctx.store_id, activity_id=activity.id, deleted_by=ctx.user_id)
        )

    def clone_template_into_programme(
        self, ctx: AuthContext, programme_id: str, template_key: str
    ) -> list[Activity]:
        if not self._programmes.exists_in_store(programme_id, ctx.store_id):
            raise NotFoundError(f"Programme '{programme_id}' not found", code="PROGRAMME_NOT_FOUND")
        definitions = PLANOGRAM_TEMPLATES.get(template_key)
        if definitions is None:
            raise ValidationError(
                f"Template '{template_key}' does not exist", code="UNKNOWN_TEMPLATE_KEY"
            )

        now = utcnow()
        created: list[Activity] = []
        for definition in definitions:
            activity = Activity(
                id=new_id("act"),
                store_id=ctx.store_id,
                title=definition.title,
                description=definition.description,
                status=ActivityStatus.TODO,
                priority=definition.priority,
                category=ActivityCategory.PLANOGRAM,
                programme_id=programme_id,
                assignee_id=None,
                created_by=ctx.user_id,
                created_at=now,
                updated_at=now,
                department=definition.department,
            )
            self._repo.add(activity)
            created.append(activity)

        self._bus.publish(
            ActivitiesTemplateCloned(
                store_id=ctx.store_id,
                programme_id=programme_id,
                template_key=template_key,
                activity_ids=tuple(a.id for a in created),
                created_by=ctx.user_id,
            )
        )
        return created

    def _ensure_assignable(self, ctx: AuthContext, assignee_id: str | None) -> None:
        if assignee_id is not None and not self._staff.is_member_of_store(
            assignee_id, ctx.store_id
        ):
            raise ValidationError(
                f"Assignee '{assignee_id}' is not a staff member of this store",
                code="UNKNOWN_ASSIGNEE",
            )
