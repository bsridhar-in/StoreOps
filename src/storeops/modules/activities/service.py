from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from storeops.core.auth import AuthContext
from storeops.core.clock import utcnow
from storeops.core.errors import (
    AppError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationError,
)
from storeops.core.events import (
    ActivitiesBulkUpdated,
    ActivitiesTemplateCloned,
    ActivityCreated,
    ActivityDeleted,
    ActivityStatusChange,
    ActivityUpdated,
    EventBus,
)
from storeops.core.ids import new_id
from storeops.modules.activities.models import (
    Activity,
    ActivityAuditEntry,
    ActivityCategory,
    ActivityStatus,
    BulkStatusItemResult,
    BulkStatusOutcome,
    BulkStatusResult,
)
from storeops.modules.activities.repository import (
    ActivityAuditRepository,
    ActivityRepository,
    InMemoryActivityAuditRepository,
)
from storeops.modules.activities.schemas import ActivityCreate, ActivityUpdate
from storeops.modules.activities.templates import PLANOGRAM_TEMPLATES
from storeops.modules.programmes import ProgrammeReader
from storeops.modules.staff import StaffReader

_NON_NULLABLE_FIELDS = frozenset({"status", "priority", "category"})
_BULK_AUDIT_SOURCE = "bulk_status"

BULK_STATUS_TARGETS = frozenset({ActivityStatus.DONE, ActivityStatus.BLOCKED})
BULK_LIMIT = 100


class ActivityService:
    def __init__(
        self,
        repo: ActivityRepository,
        staff: StaffReader,
        programmes: ProgrammeReader,
        bus: EventBus,
        *,
        audit_repo: ActivityAuditRepository | None = None,
    ) -> None:
        self._repo = repo
        self._staff = staff
        self._programmes = programmes
        self._bus = bus
        self._audit = audit_repo if audit_repo is not None else InMemoryActivityAuditRepository()

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

    def bulk_update_status(
        self,
        ctx: AuthContext,
        ids: Sequence[str],
        status: ActivityStatus,
        note: str | None = None,
    ) -> BulkStatusResult:
        if status not in BULK_STATUS_TARGETS:
            raise ValidationError(
                f"Status '{status.value}' is not allowed for a bulk update",
                code="INVALID_BULK_STATUS",
                details={"allowed": sorted(s.value for s in BULK_STATUS_TARGETS)},
            )
        if not ids:
            raise ValidationError("At least one activity id is required", code="BULK_IDS_REQUIRED")
        distinct_ids = list(dict.fromkeys(ids))
        if len(distinct_ids) > BULK_LIMIT:
            raise ValidationError(
                f"At most {BULK_LIMIT} ids per request",
                code="BULK_LIMIT_EXCEEDED",
                details={"max": BULK_LIMIT, "received": len(distinct_ids)},
            )

        results: list[BulkStatusItemResult] = []
        changes: list[ActivityStatusChange] = []
        for activity_id in distinct_ids:
            try:
                previous, updated = self._apply_bulk_status(ctx, activity_id, status, note)
            except AppError as error:
                results.append(
                    BulkStatusItemResult(
                        id=activity_id,
                        outcome=BulkStatusOutcome.FAILED,
                        code=error.code,
                        activity=None,
                    )
                )
                continue
            results.append(
                BulkStatusItemResult(
                    id=activity_id, outcome=BulkStatusOutcome.UPDATED, code=None, activity=updated
                )
            )
            changes.append(
                ActivityStatusChange(
                    activity_id=updated.id,
                    title=updated.title,
                    from_status=previous.value,
                    assignee_id=updated.assignee_id,
                )
            )

        if changes:
            self._bus.publish(
                ActivitiesBulkUpdated(
                    store_id=ctx.store_id,
                    updated_by=ctx.user_id,
                    status=status.value,
                    note=note,
                    changes=tuple(changes),
                )
            )
        return BulkStatusResult(status=status, results=results)

    def list_audit_entries(self, ctx: AuthContext, activity_id: str) -> list[ActivityAuditEntry]:
        activity = self.get_activity(ctx, activity_id)
        return sorted(self._audit.list_for_activity(activity.id), key=lambda e: e.created_at)

    def _apply_bulk_status(
        self, ctx: AuthContext, activity_id: str, status: ActivityStatus, note: str | None
    ) -> tuple[ActivityStatus, Activity]:
        activity = self.get_activity(ctx, activity_id)
        if activity.status == status:
            raise ConflictError(
                f"Activity '{activity_id}' is already {status.value}", code="STATUS_UNCHANGED"
            )
        now = utcnow()
        updated = replace(activity, status=status, updated_at=now)
        self._repo.update(updated)
        self._audit.add(
            ActivityAuditEntry(
                id=new_id("aud"),
                store_id=ctx.store_id,
                activity_id=updated.id,
                actor_id=ctx.user_id,
                from_status=activity.status,
                to_status=status,
                note=note,
                source=_BULK_AUDIT_SOURCE,
                created_at=now,
            )
        )
        return activity.status, updated

    def _ensure_assignable(self, ctx: AuthContext, assignee_id: str | None) -> None:
        if assignee_id is not None and not self._staff.is_member_of_store(
            assignee_id, ctx.store_id
        ):
            raise ValidationError(
                f"Assignee '{assignee_id}' is not a staff member of this store",
                code="UNKNOWN_ASSIGNEE",
            )
