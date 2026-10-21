import pytest

from storeops.core.errors import (
    AppError,
    ConflictError,
    ForbiddenError,
    InternalError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from storeops.core.events import DomainEvent, EventBus, ProgrammeCreated


@pytest.mark.parametrize(
    ("error_cls", "code", "status"),
    [
        (ValidationError, "VALIDATION_ERROR", 422),
        (UnauthorizedError, "UNAUTHORIZED", 401),
        (ForbiddenError, "FORBIDDEN", 403),
        (NotFoundError, "NOT_FOUND", 404),
        (ConflictError, "CONFLICT", 409),
        (InternalError, "INTERNAL_ERROR", 500),
    ],
)
def test_error_defaults(error_cls: type[AppError], code: str, status: int) -> None:
    error = error_cls("boom")

    assert isinstance(error, AppError)
    assert error.to_dict() == {"code": code, "message": "boom", "statusCode": status}


def test_error_custom_code_and_details() -> None:
    error = NotFoundError("missing", code="THING_NOT_FOUND", details={"id": "x"})

    assert error.to_dict() == {
        "code": "THING_NOT_FOUND",
        "message": "missing",
        "statusCode": 404,
        "details": {"id": "x"},
    }


def _event() -> ProgrammeCreated:
    return ProgrammeCreated(store_id="s1", programme_id="p1", name="P", created_by="u")


def test_event_bus_dispatches_by_exact_type() -> None:
    bus = EventBus()
    received: list[DomainEvent] = []
    bus.subscribe(ProgrammeCreated, received.append)
    bus.subscribe(DomainEvent, lambda _e: received.append(_e))

    event = _event()
    bus.publish(event)

    assert received == [event]


def test_event_bus_isolates_failing_handlers() -> None:
    bus = EventBus()
    received: list[ProgrammeCreated] = []

    def failing(_event: ProgrammeCreated) -> None:
        raise InternalError("handler failed")

    bus.subscribe(ProgrammeCreated, failing)
    bus.subscribe(ProgrammeCreated, received.append)

    bus.publish(_event())

    assert len(received) == 1
