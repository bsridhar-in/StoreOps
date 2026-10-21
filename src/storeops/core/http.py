"""Translate :class:`AppError` (and framework validation errors) into JSON responses."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from storeops.core.errors import AppError, InternalError, ValidationError


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(RequestValidationError, _handle_request_validation_error)


def _error_response(error: AppError) -> JSONResponse:
    return JSONResponse(status_code=error.status_code, content={"error": error.to_dict()})


async def _handle_app_error(_request: Request, exc: Exception) -> JSONResponse:
    error = exc if isinstance(exc, AppError) else InternalError("Unexpected error")
    return _error_response(error)


async def _handle_request_validation_error(_request: Request, exc: Exception) -> JSONResponse:
    raw_errors = exc.errors() if isinstance(exc, RequestValidationError) else []
    errors = [
        {"loc": list(err.get("loc", ())), "msg": str(err.get("msg", "")), "type": err.get("type")}
        for err in raw_errors
    ]
    return _error_response(ValidationError("Request validation failed", details={"errors": errors}))
