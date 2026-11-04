"""Create a reservation, allocate seats and enqueue sync in one transaction."""

from app.database.connection import get_connection
from app.repositories import outbox_repository, reservation_repository, session_repository
from app.schemas.reservation import ReservationCreate, ReservationResponse
from app.services.session_service import SessionNotFoundError


class IdempotencyConflictError(Exception):
    """This source reference already belongs to a different session or quantity."""


class ReservationUnavailableError(Exception):
    """The session is not open or does not have enough seats."""

    
def create_reservation(data: ReservationCreate) -> tuple[ReservationResponse, bool]:
    #if bool is False, it means the no new reservation was created, not that the demand was False.
    #Return the reservation and whether this call created it.
    session_id = data.session_id
    source_ref = data.source_ref
    with get_connection() as connection:
        # Check that the session exists before attempting to insert a reservation."""
        if session_repository.get_session(connection, session_id) is None:
            raise SessionNotFoundError(session_id)
        # Attempt to insert a new reservation. If it already exists, check that it matches the request."""
        reservation = reservation_repository.create_reservation(
            connection, session_id, data.quantity, data.source, data.source_ref
        )
        # If the reservation created failed, it means a reservation with the same source_ref already exists. 
        # We need to check if it matches the current request.
        if reservation is None:
            reservation = reservation_repository.get_by_source_ref(connection, data.source, data.source_ref)
            if reservation["session_id"] != session_id or reservation["quantity"] != data.quantity:
                raise IdempotencyConflictError(source_ref)
            # A retry also returns a cancelled reservation without reviving it.
            return ReservationResponse(**reservation), False

        if not session_repository.reserve_seats(connection, session_id, data.quantity):
            # Leaving the connection context with an exception rolls back the
            # newly inserted reservation as well as any other transaction writes.
            raise ReservationUnavailableError(session_id)

        if data.source == "daisy":
            outbox_repository.create_outbox_event(connection, session_id)
        return ReservationResponse(**reservation), True
