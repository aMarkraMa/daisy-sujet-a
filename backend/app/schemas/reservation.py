"""Daisy reservation request and response models."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReservationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: UUID
    quantity: int = Field(gt=0, le=2_147_483_647, strict=True)
    source: str = Field(min_length=1, max_length=255, pattern=r"^\S+$")
    source_ref: str = Field(min_length=1, max_length=255, pattern=r"^\S+$")


class ReservationResponse(BaseModel):
    id: UUID
    session_id: UUID
    source: str
    source_ref: str
    quantity: int
    status: Literal["confirmed", "cancelled"]
    created_at: datetime
    updated_at: datetime
