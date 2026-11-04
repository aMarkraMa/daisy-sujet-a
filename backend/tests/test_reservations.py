"""Reservation HTTP contract; database behavior is tested separately."""

from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.schemas.reservation import ReservationResponse
from app.services import reservation_service
from main import app


def payload(reservation, **changes):
    return {
        "session_id": str(reservation.session_id),
        "quantity": 2,
        "source": "daisy",
        "source_ref": "request-1",
        **changes,
    }


@pytest.fixture
def api(monkeypatch):
    now = datetime.now(timezone.utc)
    reservation = ReservationResponse(
        id=uuid4(), session_id=uuid4(), source="daisy", source_ref="request-1",
        quantity=2, status="confirmed", created_at=now, updated_at=now,
    )
    create = MagicMock(return_value=(reservation, True))
    monkeypatch.setattr(reservation_service, "create_reservation", create)
    with TestClient(app) as client:
        yield client, create, reservation


@pytest.mark.parametrize("created,expected_status", [(True, 201), (False, 200)])
@pytest.mark.parametrize("source", ["daisy", "artisia-demo"])
def test_new_booking_and_replay_responses(api, created, expected_status, source):
    client, create, reservation = api
    reservation = reservation.model_copy(update={"source": source})
    create.return_value = reservation, created
    response = client.post("/reservations", json=payload(reservation, source=source))
    assert response.status_code == expected_status
    assert response.json() == reservation.model_dump(mode="json")
    args = create.call_args.args
    assert len(args) == 1
    assert args[0].session_id == reservation.session_id
    assert args[0].quantity == 2
    assert args[0].source == source
    assert args[0].source_ref == "request-1"


@pytest.mark.parametrize("body", [
    {}, {"quantity": 0}, {"quantity": -1}, {"quantity": True},
    {"quantity": 1.5}, {"quantity": "2"}, {"quantity": 2_147_483_648},
    {"quantity": 2, "status": "confirmed"},
])
def test_invalid_body_is_rejected_before_business_logic(api, body):
    client, create, reservation = api
    response = client.post("/reservations", json={
        "session_id": str(reservation.session_id), "source": "daisy",
        "source_ref": "request-1", **body,
    })
    assert response.status_code == 422
    create.assert_not_called()


@pytest.mark.parametrize("key", [None, "", "   ", "has space", "x" * 256])
@pytest.mark.parametrize("field", ["source", "source_ref"])
def test_invalid_or_missing_source_fields(api, field, key):
    client, create, reservation = api
    body = payload(reservation, **{field: key})
    if key is None:
        del body[field]
    response = client.post("/reservations", json=body)
    assert response.status_code == 422
    create.assert_not_called()


@pytest.mark.parametrize("session_id", [None, "not-a-uuid"])
def test_invalid_or_missing_session_id(api, session_id):
    client, create, reservation = api
    body = payload(reservation, session_id=session_id)
    if session_id is None:
        del body["session_id"]
    response = client.post("/reservations", json=body)
    assert response.status_code == 422
    create.assert_not_called()


@pytest.mark.parametrize("error,expected_status", [
    (reservation_service.SessionNotFoundError, 404),
    (reservation_service.IdempotencyConflictError, 409),
    (reservation_service.ReservationUnavailableError, 409),
])
def test_business_errors_are_translated_to_http(api, error, expected_status):
    client, create, reservation = api
    create.side_effect = error()
    response = client.post("/reservations", json=payload(reservation))
    assert response.status_code == expected_status
    assert response.json()["detail"]
