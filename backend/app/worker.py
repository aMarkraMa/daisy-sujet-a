"""Send pending webhook and outbox tasks to the Daisy and Artisia APIs."""

import os
import time

import httpx

from app.database.connection import get_connection
from app.repositories import outbox_repository, partner_session_repository, session_repository, webhook_repository


def process_one_webhook(event: dict) -> None:
    # Only booking creation has a corresponding Daisy API for now.
    if event["event_type"] != "booking.created":
        return
    data = event["payload"]["data"]
    with get_connection() as connection:
        session_id = partner_session_repository.get_session_id(
            connection, event["partner_id"], data["session_id"],
        )
    if session_id is None:
        raise ValueError("Partner session mapping not found")

    base_url = os.environ.get("DAISY_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    response = httpx.post(
        f"{base_url}/reservations",
        json={
            "session_id": str(session_id), "quantity": data["seats"],
            "source": event["partner_id"], "source_ref": data["booking_id"],
        },
        timeout=5,
    )
    response.raise_for_status()
    with get_connection() as connection:
        webhook_repository.mark_processed(connection, event["partner_id"], event["event_id"])


def process_one_outbox(event: dict) -> None:
    with get_connection() as connection:
        inventory = session_repository.get_inventory_for_partner(
            connection, event["session_id"], event["partner_id"],
        )
        outbox_repository.increment_attempts(connection, event["id"])

    capacity = max(0, inventory["capacity"] - inventory["booked_seats"] + inventory["partner_booked"])
    status = "published" if inventory["sales_state"] == "open" else inventory["sales_state"]
    base_url = os.environ.get("ARTISIA_BASE_URL", "http://127.0.0.1:8001/v1").rstrip("/")
    api_key = os.environ.get("ARTISIA_API_KEY", "artisia-demo-key")

    # The worker calls the FastAPI endpoint over HTTP.
    response = httpx.patch(
        f"{base_url}/sessions/{event['partner_session_id']}",
        headers={"Authorization": f"Bearer {api_key}"},
        json={"capacity": capacity, "status": status},
        timeout=5,
    )
    response.raise_for_status()
    remote = response.json()

    with get_connection() as connection:
        partner_session_repository.update_partner_session(
            connection, event["session_id"], event["partner_id"],
            remote["capacity"], remote["booked"], remote["status"],
        )
        outbox_repository.mark_processed(connection, event["id"])



def main():
    while True:
        with get_connection() as connection:
            webhooks = webhook_repository.get_pending_events(
                connection, os.environ.get("ARTISIA_PARTNER_ID", "artisia"),
            )
            events = outbox_repository.get_pending_events(
                connection, os.environ.get("ARTISIA_PARTNER_ID", "artisia"),
            )
        for event in webhooks:
            process_one_webhook(event)
            time.sleep(1)
        for event in events:
            process_one_outbox(event)
            time.sleep(1)
        time.sleep(1)


if __name__ == "__main__":
    main()
