from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class AlertType(StrEnum):
    ACTIVITY_ASSIGNED = "activity_assigned"
    ACTIVITY_STATUS_CHANGED = "activity_status_changed"
    PROGRAMME_MEMBER_ADDED = "programme_member_added"


@dataclass
class Alert:
    id: str
    store_id: str
    recipient_id: str
    type: AlertType
    message: str
    source_id: str
    created_at: datetime
    read: bool = False
