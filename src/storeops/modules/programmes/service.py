from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from storeops.core.auth import AuthContext
from storeops.core.clock import utcnow
from storeops.core.errors import ConflictError, NotFoundError, ValidationError
from storeops.core.events import EventBus, ProgrammeCreated, ProgrammeMemberAdded
from storeops.core.ids import new_id
from storeops.modules.programmes.models import Programme
from storeops.modules.programmes.repository import ProgrammeRepository
from storeops.modules.programmes.schemas import AddMemberRequest, ProgrammeCreate
from storeops.modules.staff import StaffReader


class ProgrammeReader(Protocol):
    """Read-only programme lookup exposed to other modules."""

    def exists_in_store(self, programme_id: str, store_id: str) -> bool: ...


class ProgrammeService:
    def __init__(self, repo: ProgrammeRepository, staff: StaffReader, bus: EventBus) -> None:
        self._repo = repo
        self._staff = staff
        self._bus = bus

    def list_programmes(self, ctx: AuthContext) -> list[Programme]:
        return self._repo.list_by_store(ctx.store_id)

    def create_programme(self, ctx: AuthContext, data: ProgrammeCreate) -> Programme:
        programme = Programme(
            id=new_id("prg"),
            store_id=ctx.store_id,
            name=data.name,
            description=data.description,
            start_date=data.start_date,
            end_date=data.end_date,
            created_by=ctx.user_id,
            created_at=utcnow(),
        )
        self._repo.add(programme)
        self._bus.publish(
            ProgrammeCreated(
                store_id=ctx.store_id,
                programme_id=programme.id,
                name=programme.name,
                created_by=ctx.user_id,
            )
        )
        return programme

    def add_member(self, ctx: AuthContext, programme_id: str, data: AddMemberRequest) -> Programme:
        programme = self._get_in_store(programme_id, ctx.store_id)
        if not self._staff.is_member_of_store(data.staff_id, ctx.store_id):
            raise ValidationError(
                f"Staff member '{data.staff_id}' does not belong to this store",
                code="UNKNOWN_STAFF_MEMBER",
            )
        if data.staff_id in programme.member_ids:
            raise ConflictError(
                f"Staff member '{data.staff_id}' is already in this programme",
                code="ALREADY_A_MEMBER",
            )
        updated = replace(programme, member_ids=[*programme.member_ids, data.staff_id])
        self._repo.update(updated)
        self._bus.publish(
            ProgrammeMemberAdded(
                store_id=ctx.store_id,
                programme_id=updated.id,
                programme_name=updated.name,
                staff_id=data.staff_id,
                added_by=ctx.user_id,
            )
        )
        return updated

    def exists_in_store(self, programme_id: str, store_id: str) -> bool:
        programme = self._repo.get(programme_id)
        return programme is not None and programme.store_id == store_id

    def _get_in_store(self, programme_id: str, store_id: str) -> Programme:
        programme = self._repo.get(programme_id)
        if programme is None or programme.store_id != store_id:
            raise NotFoundError(f"Programme '{programme_id}' not found", code="PROGRAMME_NOT_FOUND")
        return programme
