"""Create a demo session and its Artisia mapping: python -m app.database.seed_demo."""

from uuid import UUID

from app.database.connection import get_connection


# Fixed identifiers make this script safe to run again.
SESSION_ID = UUID("44710000-0000-4000-8000-000000000001")
PARTNER_ID = "artisia"
PARTNER_SESSION_ID = "art_ses_8812"
TITLE = "Tour de potier débutant"
STARTS_AT = "2027-01-16T14:00:00+01:00"
DURATION_MINUTES = 120
CAPACITY = 8


def seed_demo(connection):
    connection.execute(
        """INSERT INTO sessions (id, title, starts_at, duration_minutes, capacity)
           VALUES (%s, %s, %s, %s, %s)""",
        (SESSION_ID, TITLE, STARTS_AT, DURATION_MINUTES, CAPACITY),
    )

    mapping = connection.execute(
        """INSERT INTO partner_sessions (session_id, partner_id, partner_session_id)
           VALUES (%s, %s, %s)
           ON CONFLICT (session_id, partner_id) DO NOTHING
           RETURNING partner_session_id""",
        (SESSION_ID, PARTNER_ID, PARTNER_SESSION_ID),
    ).fetchone()


def main():
    with get_connection() as connection:
        seed_demo(connection)
    print(f"Demo session ready: {SESSION_ID}")
    print(f"Partner: {PARTNER_ID}, partner session: {PARTNER_SESSION_ID}")


if __name__ == "__main__":
    main()
