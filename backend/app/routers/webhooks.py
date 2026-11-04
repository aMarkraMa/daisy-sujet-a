"""HTTP endpoints for creating and listing pending webhook events."""

from fastapi import APIRouter

from app.schemas.webhook import WebhookEventCreate
from app.services import webhook_service

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/{partner_id}", status_code=202)
def create_webhook_event(partner_id: str, event: WebhookEventCreate):
    return {"created": webhook_service.create_webhook_event(partner_id, event)}


@router.get("/{partner_id}/pending")
def get_pending_events(partner_id: str):
    return webhook_service.get_pending_events(partner_id)
