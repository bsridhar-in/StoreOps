from typing import Annotated

from fastapi import APIRouter, Depends, Request

from storeops.core.auth import Auth
from storeops.modules.programmes.schemas import AddMemberRequest, ProgrammeCreate, ProgrammeOut
from storeops.modules.programmes.service import ProgrammeService

router = APIRouter(prefix="/api/programmes", tags=["programmes"])


def get_programme_service(request: Request) -> ProgrammeService:
    service: ProgrammeService = request.app.state.programme_service
    return service


Service = Annotated[ProgrammeService, Depends(get_programme_service)]


@router.get("")
async def list_programmes(ctx: Auth, service: Service) -> list[ProgrammeOut]:
    return [ProgrammeOut.model_validate(p) for p in service.list_programmes(ctx)]


@router.post("", status_code=201)
async def create_programme(body: ProgrammeCreate, ctx: Auth, service: Service) -> ProgrammeOut:
    return ProgrammeOut.model_validate(service.create_programme(ctx, body))


@router.post("/{programme_id}/members", status_code=201)
async def add_programme_member(
    programme_id: str, body: AddMemberRequest, ctx: Auth, service: Service
) -> ProgrammeOut:
    return ProgrammeOut.model_validate(service.add_member(ctx, programme_id, body))
