from datetime import date, datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProgrammeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def _check_date_range(self) -> Self:
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class AddMemberRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    staff_id: str = Field(min_length=1)


class ProgrammeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    store_id: str
    name: str
    description: str
    start_date: date | None
    end_date: date | None
    member_ids: list[str]
    created_by: str
    created_at: datetime
