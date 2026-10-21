"""Store and region metrics, accumulated from domain events (no direct module imports)."""

from __future__ import annotations

from collections.abc import Sequence

from storeops.core.events import (
    ActivitiesBulkUpdated,
    ActivityCreated,
    ActivityDeleted,
    ActivityUpdated,
    EventBus,
    ProgrammeCreated,
    ProgrammeMemberAdded,
)
from storeops.modules.reports.models import RegionMetrics, StoreMetrics
from storeops.modules.reports.repository import MetricsRepository

_DONE_STATUS = "done"


class ReportService:
    def __init__(self, repo: MetricsRepository) -> None:
        self._repo = repo

    def register(self, bus: EventBus) -> None:
        bus.subscribe(ActivityCreated, self._on_activity_created)
        bus.subscribe(ActivityUpdated, self._on_activity_updated)
        bus.subscribe(ActivitiesBulkUpdated, self._on_activities_bulk_updated)
        bus.subscribe(ActivityDeleted, self._on_activity_deleted)
        bus.subscribe(ProgrammeCreated, self._on_programme_created)
        bus.subscribe(ProgrammeMemberAdded, self._on_programme_member_added)

    def get_store_metrics(self, store_id: str) -> StoreMetrics:
        return self._repo.get(store_id) or StoreMetrics(store_id=store_id)

    def get_region_metrics(self, region_id: str, store_ids: Sequence[str]) -> RegionMetrics:
        stores = [self.get_store_metrics(store_id) for store_id in store_ids]
        return RegionMetrics(
            region_id=region_id,
            store_count=len(stores),
            activities_created=sum(m.activities_created for m in stores),
            activities_completed=sum(m.activities_completed for m in stores),
            activities_deleted=sum(m.activities_deleted for m in stores),
            programmes_created=sum(m.programmes_created for m in stores),
            programme_members_added=sum(m.programme_members_added for m in stores),
        )

    # -- event handlers ---------------------------------------------------------------

    def _on_activity_created(self, event: ActivityCreated) -> None:
        metrics = self.get_store_metrics(event.store_id)
        metrics.activities_created += 1
        self._repo.save(metrics)

    def _on_activity_updated(self, event: ActivityUpdated) -> None:
        if "status" in event.changed_fields and event.status == _DONE_STATUS:
            metrics = self.get_store_metrics(event.store_id)
            metrics.activities_completed += 1
            self._repo.save(metrics)

    def _on_activities_bulk_updated(self, event: ActivitiesBulkUpdated) -> None:
        if event.status == _DONE_STATUS and event.changes:
            metrics = self.get_store_metrics(event.store_id)
            metrics.activities_completed += len(event.changes)
            self._repo.save(metrics)

    def _on_activity_deleted(self, event: ActivityDeleted) -> None:
        metrics = self.get_store_metrics(event.store_id)
        metrics.activities_deleted += 1
        self._repo.save(metrics)

    def _on_programme_created(self, event: ProgrammeCreated) -> None:
        metrics = self.get_store_metrics(event.store_id)
        metrics.programmes_created += 1
        self._repo.save(metrics)

    def _on_programme_member_added(self, event: ProgrammeMemberAdded) -> None:
        metrics = self.get_store_metrics(event.store_id)
        metrics.programme_members_added += 1
        self._repo.save(metrics)
