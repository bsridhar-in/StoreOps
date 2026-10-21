from __future__ import annotations

from typing import Protocol

from storeops.modules.programmes.models import Programme


class ProgrammeRepository(Protocol):
    def add(self, programme: Programme) -> None: ...

    def get(self, programme_id: str) -> Programme | None: ...

    def list_by_store(self, store_id: str) -> list[Programme]: ...

    def update(self, programme: Programme) -> None: ...


class InMemoryProgrammeRepository:
    def __init__(self) -> None:
        self._items: dict[str, Programme] = {}

    def add(self, programme: Programme) -> None:
        self._items[programme.id] = programme

    def get(self, programme_id: str) -> Programme | None:
        return self._items.get(programme_id)

    def list_by_store(self, store_id: str) -> list[Programme]:
        return [p for p in self._items.values() if p.store_id == store_id]

    def update(self, programme: Programme) -> None:
        self._items[programme.id] = programme
