"""Enqueue partner synchronization in the caller's business transaction."""

from uuid import UUID

from psycopg import Connection


def create_outbox_event(connection: Connection, session_id: UUID) -> None:
    connection.execute(
        """INSERT INTO outbox_events (session_id, partner_id, partner_session_id)
           SELECT session_id, partner_id, partner_session_id
           FROM partner_sessions
           WHERE session_id = %s""",
        (session_id,),
    )


def get_pending_events(connection: Connection, partner_id: str) -> list[dict]:
    return connection.execute(
        """SELECT *
           FROM outbox_events
           WHERE status = 'pending' AND partner_id = %s
           ORDER BY id
           LIMIT 10""",
        (partner_id,),
    ).fetchall()


def increment_attempts(connection: Connection, event_id: int) -> None:
    connection.execute(
        "UPDATE outbox_events SET attempts = attempts + 1 WHERE id = %s",
        (event_id,),
    )


def mark_processed(connection: Connection, event_id: int) -> None:
    connection.execute(
        """UPDATE outbox_events SET status = 'processed', processed_at = now()
           WHERE id = %s""",
        (event_id,),
    )
