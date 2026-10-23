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


class BulkStatusOutcome(StrEnum):
    UPDATED = "updated"
    FAILED = "failed"


@dataclass(frozen=True)
class ActivityAuditEntry:
    id: str
    store_id: str
    activity_id: str
    actor_id: str
    from_status: ActivityStatus
    to_status: ActivityStatus
    note: str | None
    source: str
    created_at: datetime


@dataclass(frozen=True)
class BulkStatusItemResult:
    id: str
    outcome: BulkStatusOutcome
    code: str | None
    activity: Activity | None


@dataclass(frozen=True)
class BulkStatusResult:
    status: ActivityStatus
    results: list[BulkStatusItemResult]

    @property
    def updated_count(self) -> int:
        return sum(1 for r in self.results if r.outcome is BulkStatusOutcome.UPDATED)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if r.outcome is BulkStatusOutcome.FAILED)
