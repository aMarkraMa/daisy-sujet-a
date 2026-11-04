"""Add and backfill the partner session ID on an existing outbox table."""

from app.database.connection import get_connection


def migrate(connection):
    connection.execute("""
        ALTER TABLE outbox_events ADD COLUMN IF NOT EXISTS partner_session_id text;
        UPDATE outbox_events o
        SET partner_session_id = p.partner_session_id
        FROM partner_sessions p
        WHERE o.session_id = p.session_id AND o.partner_id = p.partner_id
          AND o.partner_session_id IS NULL;
        ALTER TABLE outbox_events ALTER COLUMN partner_session_id SET NOT NULL;
    """)


if __name__ == "__main__":
    with get_connection() as connection:
        migrate(connection)
