from __future__ import annotations

from typing import Protocol

from storeops.modules.activities.models import Activity, ActivityStatus


class ActivityRepository(Protocol):
    def add(self, activity: Activity) -> None: ...

    def get(self, activity_id: str) -> Activity | None: ...

    def list_by_store(
        self,
        store_id: str,
        *,
        programme_id: str | None = None,
        status: ActivityStatus | None = None,
    ) -> list[Activity]: ...

    def update(self, activity: Activity) -> None: ...

    def delete(self, activity_id: str) -> None: ...


class InMemoryActivityRepository:
    def __init__(self) -> None:
        self._items: dict[str, Activity] = {}

    def add(self, activity: Activity) -> None:
        self._items[activity.id] = activity

    def get(self, activity_id: str) -> Activity | None:
        return self._items.get(activity_id)

    def list_by_store(
        self,
        store_id: str,
        *,
        programme_id: str | None = None,
        status: ActivityStatus | None = None,
    ) -> list[Activity]:
        return [
            a
            for a in self._items.values()
            if a.store_id == store_id
            and (programme_id is None or a.programme_id == programme_id)
            and (status is None or a.status == status)
        ]

    def update(self, activity: Activity) -> None:
        self._items[activity.id] = activity

    def delete(self, activity_id: str) -> None:
        self._items.pop(activity_id, None)
