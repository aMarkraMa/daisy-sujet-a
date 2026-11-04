"""Insert webhook events and read pending events."""

from psycopg import Connection
from psycopg.types.json import Jsonb

from app.schemas.webhook import WebhookEventCreate


def create_webhook_event(connection: Connection, partner_id: str, event: WebhookEventCreate) -> bool:
    row = connection.execute(
        """INSERT INTO webhook_events
               (partner_id, event_id, event_type, occurred_at, payload)
           VALUES (%s, %s, %s, %s, %s)
           ON CONFLICT (partner_id, event_id) DO NOTHING
           RETURNING event_id""",
        (partner_id, event.event_id, event.type, event.occurred_at,
         Jsonb(event.model_dump(mode="json"))),
    ).fetchone()
    return row is not None


def get_pending_events(connection: Connection, partner_id: str) -> list[dict]:
    return connection.execute(
        """SELECT * FROM webhook_events
           WHERE partner_id = %s AND status = 'pending'
           ORDER BY recieved_at, event_id
           LIMIT 10""",
        (partner_id,),
    ).fetchall()


def mark_processed(connection: Connection, partner_id: str, event_id: str) -> None:
    connection.execute(
        """UPDATE webhook_events SET status = 'processed', processed_at = now()
           WHERE partner_id = %s AND event_id = %s""",
        (partner_id, event_id),
    )
