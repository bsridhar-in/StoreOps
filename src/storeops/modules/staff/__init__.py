"""Staff module - the store's user directory. Read-only for every other module."""

from storeops.modules.staff.models import StaffMember
from storeops.modules.staff.repository import DEMO_STAFF, InMemoryStaffRepository
from storeops.modules.staff.routes import router
from storeops.modules.staff.service import StaffReader, StaffService

__all__ = [
    "DEMO_STAFF",
    "InMemoryStaffRepository",
    "StaffMember",
    "StaffReader",
    "StaffService",
    "router",
]
