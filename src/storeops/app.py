"""Composition root: wires repositories, services, event subscriptions and routers.

This is the only place allowed to know about every module.
"""

from __future__ import annotations

from collections.abc import Iterable

from fastapi import FastAPI

from storeops import __version__
from storeops.core.events import EventBus
from storeops.core.http import register_error_handlers
from storeops.modules import activities, alerts, programmes, reports, staff


def create_app(*, staff_seed: Iterable[staff.StaffMember] = staff.DEMO_STAFF) -> FastAPI:
    bus = EventBus()

    staff_service = staff.StaffService(staff.InMemoryStaffRepository(staff_seed))
    programme_service = programmes.ProgrammeService(
        programmes.InMemoryProgrammeRepository(), staff_service, bus
    )
    activity_service = activities.ActivityService(
        activities.InMemoryActivityRepository(),
        staff_service,
        programme_service,
        bus,
        audit_repo=activities.InMemoryActivityAuditRepository(),
    )
    alert_service = alerts.AlertService(alerts.InMemoryAlertRepository())
    alert_service.register(bus)
    report_service = reports.ReportService(reports.InMemoryMetricsRepository())
    report_service.register(bus)

    app = FastAPI(title="StoreOps API", version=__version__)
    app.state.event_bus = bus
    app.state.staff_service = staff_service
    app.state.programme_service = programme_service
    app.state.activity_service = activity_service
    app.state.alert_service = alert_service
    app.state.report_service = report_service

    register_error_handlers(app)
    for router in (
        activities.router,
        programmes.router,
        staff.router,
        alerts.router,
        reports.router,
    ):
        app.include_router(router)
    return app
