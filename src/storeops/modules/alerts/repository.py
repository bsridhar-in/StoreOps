from __future__ import annotations

from typing import Protocol

from storeops.modules.alerts.models import Alert


class AlertRepository(Protocol):
    def add(self, alert: Alert) -> None: ...

    def list_for_recipient(self, store_id: str, recipient_id: str) -> list[Alert]: ...


class InMemoryAlertRepository:
    def __init__(self) -> None:
        self._items: dict[str, Alert] = {}

    def add(self, alert: Alert) -> None:
        self._items[alert.id] = alert

    def list_for_recipient(self, store_id: str, recipient_id: str) -> list[Alert]:
        alerts = [
            a
            for a in self._items.values()
            if a.store_id == store_id and a.recipient_id == recipient_id
        ]
        return sorted(alerts, key=lambda a: a.created_at, reverse=True)
