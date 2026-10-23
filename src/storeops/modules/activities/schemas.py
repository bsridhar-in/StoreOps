from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from storeops.modules.activities.models import (
    ActivityCategory,
    ActivityPriority,
    ActivityStatus,
    BulkStatusOutcome,
)


class ActivityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=2000)
    priority: ActivityPriority = ActivityPriority.MEDIUM
    category: ActivityCategory = ActivityCategory.OTHER
    programme_id: str | None = None
    assignee_id: str | None = None


class ActivityUpdate(BaseModel):
    """Partial update. Only fields present in the request body are applied."""

    model_config = ConfigDict(extra="forbid")

    status: ActivityStatus | None = None
    priority: ActivityPriority | None = None
    category: ActivityCategory | None = None
    assignee_id: str | None = None


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


class TemplateCloneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_key: str = "standard_planogram_reset"


class TemplateCloneOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    programme_id: str
    template_key: str
    activities: list[ActivityOut]


class BulkStatusUpdate(BaseModel):
    """Shift handover: set several activities to one status.

    The id count and allowed target statuses are business rules checked in the service so
    they return their own error codes.
    """

    model_config = ConfigDict(extra="forbid")

    ids: list[str]
    status: ActivityStatus
    note: str | None = Field(default=None, max_length=500)


class BulkStatusItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    outcome: BulkStatusOutcome
    code: str | None
    activity: ActivityOut | None


class BulkStatusResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    status: ActivityStatus
    updated_count: int
    failed_count: int
    results: list[BulkStatusItemOut]


class ActivityAuditEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    activity_id: str
    actor_id: str
    from_status: ActivityStatus
    to_status: ActivityStatus
    note: str | None
    source: str
    created_at: datetime
