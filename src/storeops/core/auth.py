"""Stub authentication.

The caller's identity is taken from request headers. This is a placeholder for a real
identity provider (e.g. JWT validation) and must not be used as-is in production:

* ``X-User-Id``  - staff member id (required)
* ``X-Store-Id`` - store the caller is acting in (required)
* ``X-Role``     - ``staff`` (default) or ``store_manager``
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated

from fastapi import Depends, Header

from storeops.core.errors import UnauthorizedError


class Role(StrEnum):
    STAFF = "staff"
    STORE_MANAGER = "store_manager"


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    store_id: str
    role: Role

    @property
    def is_store_manager(self) -> bool:
        return self.role is Role.STORE_MANAGER


def get_auth_context(
    x_user_id: Annotated[str | None, Header()] = None,
    x_store_id: Annotated[str | None, Header()] = None,
    x_role: Annotated[str | None, Header()] = None,
) -> AuthContext:
    if not x_user_id or not x_store_id:
        raise UnauthorizedError("Missing X-User-Id or X-Store-Id header")
    try:
        role = Role(x_role) if x_role else Role.STAFF
    except ValueError as exc:
        raise UnauthorizedError(f"Unknown role '{x_role}'", code="UNKNOWN_ROLE") from exc
    return AuthContext(user_id=x_user_id, store_id=x_store_id, role=role)


Auth = Annotated[AuthContext, Depends(get_auth_context)]
