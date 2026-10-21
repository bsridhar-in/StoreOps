"""Typed application error hierarchy.

Services and routes raise subclasses of :class:`AppError` only - never raw built-in
exceptions. The HTTP layer (:mod:`storeops.core.http`) translates them into a consistent
JSON error envelope::

    {"error": {"code": "NOT_FOUND", "message": "...", "statusCode": 404}}
"""

from __future__ import annotations

from typing import Any, ClassVar


class AppError(Exception):
    """Base class for all expected application errors."""

    default_code: ClassVar[str] = "INTERNAL_ERROR"
    status_code: ClassVar[int] = 500

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.default_code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "statusCode": self.status_code,
        }
        if self.details:
            body["details"] = self.details
        return body


class ValidationError(AppError):
    """The request is well-formed but semantically invalid."""

    default_code = "VALIDATION_ERROR"
    status_code = 422


class UnauthorizedError(AppError):
    """The caller is not authenticated."""

    default_code = "UNAUTHORIZED"
    status_code = 401


class ForbiddenError(AppError):
    """The caller is authenticated but not allowed to perform the action."""

    default_code = "FORBIDDEN"
    status_code = 403


class NotFoundError(AppError):
    """The requested resource does not exist (or is not visible to the caller)."""

    default_code = "NOT_FOUND"
    status_code = 404


class ConflictError(AppError):
    """The request conflicts with the current state of the resource."""

    default_code = "CONFLICT"
    status_code = 409


class InternalError(AppError):
    """An unexpected failure; details are never leaked to the client."""

    default_code = "INTERNAL_ERROR"
    status_code = 500
