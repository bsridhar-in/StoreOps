from dataclasses import dataclass

from storeops.core.auth import Role


@dataclass(frozen=True)
class StaffMember:
    id: str
    store_id: str
    name: str
    role: Role
