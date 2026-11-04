"""Webhook event input."""

from pydantic import AwareDatetime, BaseModel, Field


class WebhookEventCreate(BaseModel):
    event_id: str = Field(min_length=1)
    type: str = Field(min_length=1)
    occurred_at: AwareDatetime
    data: dict
