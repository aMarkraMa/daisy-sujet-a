"""Artisia mock data, separate from Daisy's PostgreSQL database."""

from datetime import datetime, timezone
from uuid import uuid4


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


# Run one API process. Restarting it resets these dictionaries.
sessions = {
    "art_ses_8812": {
        "session_id": "art_ses_8812",
        "external_ref": "44710000-0000-4000-8000-000000000001",
        "title": "Tour de potier débutant",
        "starts_at": "2027-01-16T14:00:00+01:00",
        "duration_minutes": 120,
        "capacity": 8,
        "booked": 0,
        "status": "published",
        "updated_at": timestamp(),
    },
}
bookings = {}


def list_sessions() -> list[dict]:
    return [session.copy() for session in sessions.values()]


def get_session(session_id: str) -> dict | None:
    session = sessions.get(session_id)
    return session.copy() if session is not None else None


def update_session(session_id: str, changes: dict) -> dict:
    sessions[session_id].update(changes)
    sessions[session_id]["updated_at"] = timestamp()
    return sessions[session_id].copy()


def create_booking(session_id: str, data: dict) -> dict:
    # external_ref is not an idempotency key on Artisia.
    booking_id = "art_bk_" + uuid4().hex
    bookings[booking_id] = {**data, "session_id": session_id, "status": "confirmed"}
    sessions[session_id]["booked"] += data["seats"]
    sessions[session_id]["updated_at"] = timestamp()
    return {"booking_id": booking_id, "seats": data["seats"], "status": "confirmed"}


def get_booking(booking_id: str) -> dict | None:
    booking = bookings.get(booking_id)
    return booking.copy() if booking is not None else None


def cancel_booking(booking_id: str) -> None:
    booking = bookings[booking_id]
    booking["status"] = "cancelled"
    sessions[booking["session_id"]]["booked"] -= booking["seats"]
    sessions[booking["session_id"]]["updated_at"] = timestamp()
