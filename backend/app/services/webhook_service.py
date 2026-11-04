"""Manage transactions for webhook event creation and reading."""

from app.database.connection import get_connection
from app.repositories import webhook_repository
from app.schemas.webhook import WebhookEventCreate


def create_webhook_event(partner_id: str, event: WebhookEventCreate) -> bool:
    with get_connection() as connection:
        return webhook_repository.create_webhook_event(connection, partner_id, event)


def get_pending_events(partner_id: str) -> list[dict]:
    with get_connection() as connection:
        return webhook_repository.get_pending_events(connection, partner_id)
