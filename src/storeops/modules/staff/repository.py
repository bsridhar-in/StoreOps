from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol

from storeops.core.auth import Role
from storeops.modules.staff.models import StaffMember

DEMO_STAFF: tuple[StaffMember, ...] = (
    StaffMember(id="staff-mgr-1", store_id="store-001", name="Maya Patel", role=Role.STORE_MANAGER),
    StaffMember(id="staff-001", store_id="store-001", name="Alex Chen", role=Role.STAFF),
    StaffMember(id="staff-002", store_id="store-001", name="Sam Rivera", role=Role.STAFF),
    StaffMember(id="staff-mgr-2", store_id="store-002", name="Jordan Lee", role=Role.STORE_MANAGER),
    StaffMember(id="staff-101", store_id="store-002", name="Priya Nair", role=Role.STAFF),
)


class StaffRepository(Protocol):
    def get(self, staff_id: str) -> StaffMember | None: ...

    def list_by_store(self, store_id: str) -> list[StaffMember]: ...


class InMemoryStaffRepository:
    def __init__(self, seed: Iterable[StaffMember] = ()) -> None:
        self._items: dict[str, StaffMember] = {member.id: member for member in seed}

    def get(self, staff_id: str) -> StaffMember | None:
        return self._items.get(staff_id)

    def list_by_store(self, store_id: str) -> list[StaffMember]:
        return [member for member in self._items.values() if member.store_id == store_id]
