"""SQL for partner session observations; the caller owns the transaction."""

from uuid import UUID

from psycopg import Connection


def get_session_id(connection: Connection, partner_id: str, partner_session_id: str) -> UUID | None:
    row = connection.execute(
        """SELECT session_id FROM partner_sessions
           WHERE partner_id = %s AND partner_session_id = %s""",
        (partner_id, partner_session_id),
    ).fetchone()
    return row["session_id"] if row else None


def update_partner_session(
    connection: Connection,
    session_id: UUID,
    partner_id: str,
    capacity: int,
    booked: int,
    status: str,
) -> None:
    connection.execute(
        """UPDATE partner_sessions
           SET observed_capacity = %s, observed_booked = %s, observed_status = %s,
               observed_at = now(), last_pushed_at = now()
           WHERE session_id = %s AND partner_id = %s""",
        (capacity, booked, status, session_id, partner_id),
    )
