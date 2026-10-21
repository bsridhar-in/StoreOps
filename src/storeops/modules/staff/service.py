from __future__ import annotations

from typing import Protocol

from storeops.modules.staff.models import StaffMember
from storeops.modules.staff.repository import StaffRepository


class StaffReader(Protocol):
    """Read-only view of the staff directory - the only staff API other modules may use."""

    def get_member(self, staff_id: str, store_id: str) -> StaffMember | None: ...

    def is_member_of_store(self, staff_id: str, store_id: str) -> bool: ...


class StaffService:
    def __init__(self, repo: StaffRepository) -> None:
        self._repo = repo

    def get_member(self, staff_id: str, store_id: str) -> StaffMember | None:
        member = self._repo.get(staff_id)
        return member if member is not None and member.store_id == store_id else None

    def is_member_of_store(self, staff_id: str, store_id: str) -> bool:
        return self.get_member(staff_id, store_id) is not None

    def list_for_store(self, store_id: str) -> list[StaffMember]:
        return self._repo.list_by_store(store_id)
