"""Session operations; each operation owns its database transaction."""

from uuid import UUID

from app.database.connection import get_connection
from app.repositories import session_repository
from app.schemas.session import SessionCreate, SessionResponse


class SessionNotFoundError(Exception):
    """The requested session does not exist."""


def create_session(data: SessionCreate) -> SessionResponse:
    with get_connection() as connection:
        session = session_repository.create_session(connection, **data.model_dump())
        return SessionResponse(**session)


def get_session(session_id: UUID) -> SessionResponse:
    with get_connection() as connection:
        session = session_repository.get_session(connection, session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return SessionResponse(**session)
