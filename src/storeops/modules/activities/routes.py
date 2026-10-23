from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from storeops.core.auth import Auth
from storeops.modules.activities.models import ActivityStatus
from storeops.modules.activities.schemas import (
    ActivityCreate,
    ActivityOut,
    ActivityUpdate,
    TemplateCloneOut,
    TemplateCloneRequest,
)
from storeops.modules.activities.service import ActivityService

router = APIRouter(prefix="/api/activities", tags=["activities"])
templates_router = APIRouter(tags=["activities"])


def get_activity_service(request: Request) -> ActivityService:
    service: ActivityService = request.app.state.activity_service
    return service


Service = Annotated[ActivityService, Depends(get_activity_service)]


@router.get("")
async def list_activities(
    ctx: Auth,
    service: Service,
    programme_id: Annotated[str | None, Query()] = None,
    status: Annotated[ActivityStatus | None, Query()] = None,
) -> list[ActivityOut]:
    activities = service.list_activities(ctx, programme_id=programme_id, status=status)
    return [ActivityOut.model_validate(a) for a in activities]


@router.post("", status_code=201)
async def create_activity(body: ActivityCreate, ctx: Auth, service: Service) -> ActivityOut:
    return ActivityOut.model_validate(service.create_activity(ctx, body))


@router.get("/{activity_id}")
async def get_activity(activity_id: str, ctx: Auth, service: Service) -> ActivityOut:
    return ActivityOut.model_validate(service.get_activity(ctx, activity_id))


@router.patch("/{activity_id}")
async def update_activity(
    activity_id: str, body: ActivityUpdate, ctx: Auth, service: Service
) -> ActivityOut:
    return ActivityOut.model_validate(service.update_activity(ctx, activity_id, body))


@router.delete("/{activity_id}", status_code=204)
async def delete_activity(activity_id: str, ctx: Auth, service: Service) -> None:
    service.delete_activity(ctx, activity_id)


@templates_router.post("/api/programmes/{programme_id}/templates", status_code=201)
async def clone_template_into_programme(
    programme_id: str, body: TemplateCloneRequest, ctx: Auth, service: Service
) -> TemplateCloneOut:
    activities = service.clone_template_into_programme(ctx, programme_id, body.template_key)
    return TemplateCloneOut(
        programme_id=programme_id,
        template_key=body.template_key,
        activities=[ActivityOut.model_validate(a) for a in activities],
    )
