from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class Programme:
    id: str
    store_id: str
    name: str
    description: str
    start_date: date | None
    end_date: date | None
    created_by: str
    created_at: datetime
    member_ids: list[str] = field(default_factory=list)
