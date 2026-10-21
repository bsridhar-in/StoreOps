"""Reports HTTP routes.

No public report endpoints are in scope for v1; the router is mounted so endpoints can be
added without touching the composition root.
"""

from fastapi import APIRouter, Request

from storeops.modules.reports.service import ReportService

router = APIRouter(prefix="/api/reports", tags=["reports"])


def get_report_service(request: Request) -> ReportService:
    service: ReportService = request.app.state.report_service
    return service
