from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from storeops.core.auth import Auth
from storeops.modules.alerts.schemas import AlertOut
from storeops.modules.alerts.service import AlertService

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def get_alert_service(request: Request) -> AlertService:
    service: AlertService = request.app.state.alert_service
    return service


Service = Annotated[AlertService, Depends(get_alert_service)]


@router.get("")
async def list_alerts(
    ctx: Auth,
    service: Service,
    unread_only: Annotated[bool, Query()] = False,
) -> list[AlertOut]:
    return [AlertOut.model_validate(a) for a in service.list_for_user(ctx, unread_only=unread_only)]
