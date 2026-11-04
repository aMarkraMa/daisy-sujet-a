"""Basic Artisia rules applied to the in-memory mock data."""

from artisia_app.repositories import artisia_repository
from artisia_app.schemas.artisia import BookingCreate, SessionPatch


class ArtisiaNotFoundError(Exception):
    """The requested session or active booking does not exist."""


class ArtisiaConflictError(Exception):
    def __init__(self, detail: dict):
        self.detail = detail
        super().__init__(detail["error"])


def _get_session(session_id: str) -> dict:
    session = artisia_repository.get_session(session_id)
    if session is None:
        raise ArtisiaNotFoundError(session_id)
    return session


def list_sessions() -> dict:
    return {"sessions": artisia_repository.list_sessions()}


def update_session(session_id: str, data: SessionPatch) -> dict:
    session = _get_session(session_id)
    if data.capacity is not None and data.capacity < session["booked"]:
        raise ArtisiaConflictError({"error": "capacity_below_booked", "booked": session["booked"]})
    return artisia_repository.update_session(session_id, data.model_dump(exclude_unset=True))


def create_booking(session_id: str, data: BookingCreate) -> dict:
    session = _get_session(session_id)
    if session["status"] != "published":
        raise ArtisiaConflictError({"error": "session_not_published"})
    available = session["capacity"] - session["booked"]
    if data.seats > available:
        raise ArtisiaConflictError({"error": "not_enough_seats", "available": available})
    return artisia_repository.create_booking(session_id, data.model_dump())


def cancel_booking(booking_id: str) -> None:
    booking = artisia_repository.get_booking(booking_id)
    if booking is None or booking["status"] == "cancelled":
        raise ArtisiaNotFoundError(booking_id)
    artisia_repository.cancel_booking(booking_id)
