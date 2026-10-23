from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class ActivityStatus(StrEnum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"


class ActivityPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class ActivityCategory(StrEnum):
    MERCHANDISING = "merchandising"
    INVENTORY = "inventory"
    CUSTOMER_SERVICE = "customer_service"
    COMPLIANCE = "compliance"
    MAINTENANCE = "maintenance"
    PLANOGRAM = "planogram"
    OTHER = "other"


@dataclass
class Activity:
    id: str
    store_id: str
    title: str
    description: str
    status: ActivityStatus
    priority: ActivityPriority
    category: ActivityCategory
    programme_id: str | None
    assignee_id: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime
    department: str | None = None
