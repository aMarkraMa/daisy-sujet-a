"""Reservation identity is claimed before any seats are allocated."""

from uuid import UUID

from psycopg import Connection


def create_reservation(
    connection: Connection, session_id: UUID, quantity: int, source: str, source_ref: str
) -> dict | None:
    return connection.execute(
        """INSERT INTO reservations (session_id, source, source_ref, quantity, status)
           VALUES (%s, %s, %s, %s, 'confirmed')
           ON CONFLICT (source, source_ref) DO NOTHING
           RETURNING *""",
        (session_id, source, source_ref, quantity),
    ).fetchone()


def get_by_source_ref(connection: Connection, source: str, source_ref: str) -> dict:
    # A separate statement sees the competing insert after it has committed
    # under PostgreSQL's default READ COMMITTED isolation level.
    return connection.execute(
        "SELECT * FROM reservations WHERE source = %s AND source_ref = %s",
        (source, source_ref),
    ).fetchone()
