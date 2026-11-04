"""Parameterized SQL for sessions; transactions belong to the service."""

from datetime import datetime
from uuid import UUID

from psycopg import Connection


def create_session(
    connection: Connection,
    *,
    title: str,
    starts_at: datetime,
    duration_minutes: int,
    capacity: int,
) -> dict:
    return connection.execute(
        """INSERT INTO sessions (title, starts_at, duration_minutes, capacity)
           VALUES (%s, %s, %s, %s)
           RETURNING *""",
        (title, starts_at, duration_minutes, capacity),
    ).fetchone()


def get_session(connection: Connection, session_id: UUID) -> dict | None:
    return connection.execute(
        "SELECT * FROM sessions WHERE id = %s",
        (session_id,),
    ).fetchone()


def reserve_seats(connection: Connection, session_id: UUID, quantity: int) -> bool:
    # Check and allocate in one UPDATE. Subtraction in the predicate avoids
    # overflowing an integer when a request asks for more seats than remain.
    row = connection.execute(
        """UPDATE sessions
           SET booked_seats = booked_seats + %s
           WHERE id = %s
             AND sales_state = 'open'
             AND booked_seats <= capacity - %s
           RETURNING id""",
        (quantity, session_id, quantity),
    ).fetchone()
    return row is not None


def get_inventory_for_partner(connection: Connection, session_id: UUID, partner_id: str) -> dict:
    return connection.execute(
        """SELECT capacity, booked_seats, sales_state,
                  (SELECT COALESCE(SUM(quantity), 0) FROM reservations
                   WHERE session_id = s.id AND source = %s
                     AND status = 'confirmed') AS partner_booked
           FROM sessions s
           WHERE s.id = %s""",
        (partner_id, session_id),
    ).fetchone()
