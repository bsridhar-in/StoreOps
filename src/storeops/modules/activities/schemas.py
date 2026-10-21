from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from storeops.modules.activities.models import ActivityCategory, ActivityPriority, ActivityStatus


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
