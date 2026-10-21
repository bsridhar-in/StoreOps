"""Ops alerts. Driven purely by domain events - this module imports no other module."""

from __future__ import annotations

from storeops.core.auth import AuthContext
from storeops.core.clock import utcnow
from storeops.core.events import ActivityCreated, ActivityUpdated, EventBus, ProgrammeMemberAdded
from storeops.core.ids import new_id
from storeops.modules.alerts.models import Alert, AlertType
from storeops.modules.alerts.repository import AlertRepository


class AlertService:
    def __init__(self, repo: AlertRepository) -> None:
        self._repo = repo

    def register(self, bus: EventBus) -> None:
        bus.subscribe(ActivityCreated, self._on_activity_created)
        bus.subscribe(ActivityUpdated, self._on_activity_updated)
        bus.subscribe(ProgrammeMemberAdded, self._on_programme_member_added)

    def list_for_user(self, ctx: AuthContext, *, unread_only: bool = False) -> list[Alert]:
        alerts = self._repo.list_for_recipient(ctx.store_id, ctx.user_id)
        return [a for a in alerts if not a.read] if unread_only else alerts

    # -- event handlers ---------------------------------------------------------------

    def _on_activity_created(self, event: ActivityCreated) -> None:
        if event.assignee_id and event.assignee_id != event.created_by:
            self._raise_alert(
                event.store_id,
                event.assignee_id,
                AlertType.ACTIVITY_ASSIGNED,
                f"You have been assigned '{event.title}'",
                event.activity_id,
            )

    def _on_activity_updated(self, event: ActivityUpdated) -> None:
        if not event.assignee_id or event.assignee_id == event.updated_by:
            return
        if "assignee_id" in event.changed_fields:
            self._raise_alert(
                event.store_id,
                event.assignee_id,
                AlertType.ACTIVITY_ASSIGNED,
                f"You have been assigned '{event.title}'",
                event.activity_id,
            )
        elif "status" in event.changed_fields:
            self._raise_alert(
                event.store_id,
                event.assignee_id,
                AlertType.ACTIVITY_STATUS_CHANGED,
                f"'{event.title}' is now {event.status}",
                event.activity_id,
            )

    def _on_programme_member_added(self, event: ProgrammeMemberAdded) -> None:
        if event.staff_id != event.added_by:
            self._raise_alert(
                event.store_id,
                event.staff_id,
                AlertType.PROGRAMME_MEMBER_ADDED,
                f"You have been added to programme '{event.programme_name}'",
                event.programme_id,
            )

    def _raise_alert(
        self,
        store_id: str,
        recipient_id: str,
        alert_type: AlertType,
        message: str,
        source_id: str,
    ) -> None:
        self._repo.add(
            Alert(
                id=new_id("alr"),
                store_id=store_id,
                recipient_id=recipient_id,
                type=alert_type,
                message=message,
                source_id=source_id,
                created_at=utcnow(),
            )
        )
