"""Request and response models for the Artisia mock API."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SessionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capacity: int | None = Field(default=None, ge=0, strict=True)
    status: Literal["published", "paused", "cancelled"] | None = None


class SessionResponse(BaseModel):
    session_id: str
    external_ref: str | None
    title: str
    starts_at: datetime
    duration_minutes: int
    capacity: int
    booked: int
    status: str
    updated_at: datetime


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]


class Customer(BaseModel):
    name: str = Field(min_length=1)
    email: str = Field(min_length=1)


class BookingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer: Customer
    seats: int = Field(gt=0, strict=True)
    external_ref: str = Field(min_length=1)


class BookingResponse(BaseModel):
    booking_id: str
    seats: int
    status: Literal["confirmed"]
