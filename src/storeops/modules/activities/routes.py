from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request, Response

from storeops.core.auth import Auth
from storeops.modules.activities.models import ActivityStatus
from storeops.modules.activities.schemas import (
    ActivityAuditEntryOut,
    ActivityCreate,
    ActivityOut,
    ActivityUpdate,
    BulkStatusResultOut,
    BulkStatusUpdate,
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


# Literal path declared before "/{activity_id}" so it is not captured as an activity id.
@router.patch("/bulk-status")
async def bulk_update_status(
    body: BulkStatusUpdate, ctx: Auth, service: Service, response: Response
) -> BulkStatusResultOut:
    result = BulkStatusResultOut.model_validate(
        service.bulk_update_status(ctx, body.ids, body.status, body.note)
    )
    if result.failed_count > 0:
        response.status_code = 207
    return result


@router.get("/{activity_id}")
async def get_activity(activity_id: str, ctx: Auth, service: Service) -> ActivityOut:
    return ActivityOut.model_validate(service.get_activity(ctx, activity_id))


@router.get("/{activity_id}/audit")
async def list_activity_audit(
    activity_id: str, ctx: Auth, service: Service
) -> list[ActivityAuditEntryOut]:
    entries = service.list_audit_entries(ctx, activity_id)
    return [ActivityAuditEntryOut.model_validate(e) for e in entries]


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
