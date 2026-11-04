"""Session input validation and response fields."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    title: str = Field(min_length=1, max_length=255)
    starts_at: AwareDatetime
    # PostgreSQL integer columns store values up to 2,147,483,647.
    duration_minutes: int = Field(gt=0, le=2_147_483_647, strict=True)
    capacity: int = Field(ge=0, le=2_147_483_647, strict=True)


class SessionResponse(BaseModel):
    id: UUID
    title: str
    starts_at: datetime
    duration_minutes: int
    capacity: int
    booked_seats: int
    sales_state: Literal["open", "paused", "cancelled"]
