"""Staff HTTP routes.

No public staff endpoints are in scope for v1; the router is mounted so endpoints can be
added without touching the composition root.
"""

from fastapi import APIRouter, Request

from storeops.modules.staff.service import StaffService

router = APIRouter(prefix="/api/staff", tags=["staff"])


def get_staff_service(request: Request) -> StaffService:
    service: StaffService = request.app.state.staff_service
    return service
