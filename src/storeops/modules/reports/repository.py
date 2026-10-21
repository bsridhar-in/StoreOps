from __future__ import annotations

from typing import Protocol

from storeops.modules.reports.models import StoreMetrics


class MetricsRepository(Protocol):
    def get(self, store_id: str) -> StoreMetrics | None: ...

    def save(self, metrics: StoreMetrics) -> None: ...


class InMemoryMetricsRepository:
    def __init__(self) -> None:
        self._items: dict[str, StoreMetrics] = {}

    def get(self, store_id: str) -> StoreMetrics | None:
        return self._items.get(store_id)

    def save(self, metrics: StoreMetrics) -> None:
        self._items[metrics.store_id] = metrics
