from datetime import datetime

from pydantic import BaseModel, ConfigDict

from storeops.modules.alerts.models import AlertType


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    store_id: str
    recipient_id: str
    type: AlertType
    message: str
    source_id: str
    created_at: datetime
    read: bool
