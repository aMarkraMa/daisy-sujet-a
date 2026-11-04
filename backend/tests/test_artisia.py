"""Basic behavior of the layered Artisia mock API."""

from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from artisia_app.repositories import artisia_repository
from artisia_app.main import app


SESSION_ID = "art_ses_8812"
PREFIX = "/v1"
BOOKING = {
    "customer": {"name": "Camille Roux", "email": "camille@example.com"},
    "seats": 2,
    "external_ref": "daisy_booking_9910",
}


@pytest.fixture
def partner(monkeypatch):
    monkeypatch.setattr(artisia_repository, "sessions", deepcopy(artisia_repository.sessions))
    monkeypatch.setattr(artisia_repository, "bookings", {})
    monkeypatch.setenv("ARTISIA_API_KEY", "test-key")
    with TestClient(app, headers={"Authorization": "Bearer test-key"}) as client:
        yield client


def test_lists_seeded_session(partner):
    response = partner.get(PREFIX + "/sessions")
    assert response.status_code == 200
    session = response.json()["sessions"][0]
    assert session["session_id"] == SESSION_ID
    assert session["external_ref"] == "44710000-0000-4000-8000-000000000001"
    assert (session["capacity"], session["booked"], session["status"]) == (8, 0, "published")


def test_requires_api_key():
    with TestClient(app) as client:
        assert client.get(PREFIX + "/sessions").status_code == 401


def test_patch_updates_capacity_and_status(partner):
    response = partner.patch(PREFIX + f"/sessions/{SESSION_ID}", json={"capacity": 6, "status": "paused"})
    assert response.status_code == 200
    session = partner.get(PREFIX + "/sessions").json()["sessions"][0]
    assert (session["capacity"], session["status"]) == (6, "paused")


def test_create_and_cancel_booking(partner):
    response = partner.post(PREFIX + f"/sessions/{SESSION_ID}/bookings", json=BOOKING)
    assert response.status_code == 201
    booking = response.json()
    assert (booking["seats"], booking["status"]) == (2, "confirmed")
    assert partner.get(PREFIX + "/sessions").json()["sessions"][0]["booked"] == 2
    assert partner.delete(PREFIX + "/bookings/" + booking["booking_id"]).status_code == 204
    assert partner.get(PREFIX + "/sessions").json()["sessions"][0]["booked"] == 0
    assert partner.delete(PREFIX + "/bookings/" + booking["booking_id"]).status_code == 404
    assert partner.get(PREFIX + "/sessions").json()["sessions"][0]["booked"] == 0


def test_duplicate_posts_create_distinct_bookings(partner):
    first = partner.post(PREFIX + f"/sessions/{SESSION_ID}/bookings", json=BOOKING)
    second = partner.post(PREFIX + f"/sessions/{SESSION_ID}/bookings", json=BOOKING)
    assert first.json()["booking_id"] != second.json()["booking_id"]
    assert partner.get(PREFIX + "/sessions").json()["sessions"][0]["booked"] == 4


def test_capacity_cannot_be_lowered_below_booked(partner):
    partner.post(PREFIX + f"/sessions/{SESSION_ID}/bookings", json=BOOKING)
    response = partner.patch(PREFIX + f"/sessions/{SESSION_ID}", json={"capacity": 1})
    assert response.status_code == 409
    assert response.json() == {"error": "capacity_below_booked", "booked": 2}
    assert partner.get(PREFIX + "/sessions").json()["sessions"][0]["capacity"] == 8


def test_rejects_booking_when_full(partner):
    partner.patch(PREFIX + f"/sessions/{SESSION_ID}", json={"capacity": 1})
    response = partner.post(PREFIX + f"/sessions/{SESSION_ID}/bookings", json=BOOKING)
    assert response.status_code == 409
    assert response.json() == {"error": "not_enough_seats", "available": 1}
    session = partner.get(PREFIX + "/sessions").json()["sessions"][0]
    assert (session["booked"], session["status"]) == (0, "published")


@pytest.mark.parametrize("status", ["paused", "cancelled"])
def test_closed_session_rejects_booking(partner, status):
    partner.patch(PREFIX + f"/sessions/{SESSION_ID}", json={"status": status})
    response = partner.post(PREFIX + f"/sessions/{SESSION_ID}/bookings", json=BOOKING)
    assert response.status_code == 409
    assert response.json() == {"error": "session_not_published"}


@pytest.mark.parametrize("data", [{}, {"capacity": None}, {"capacity": -1}, {"capacity": True},
                                      {"title": "Cannot change"}, {"status": "unknown"}])
def test_patch_rejects_invalid_changes(partner, data):
    response = partner.patch(PREFIX + f"/sessions/{SESSION_ID}", json=data)
    assert response.status_code == 422


def test_unknown_resources_return_404(partner):
    assert partner.patch(PREFIX + "/sessions/missing", json={"capacity": 6}).status_code == 404
    assert partner.post(PREFIX + "/sessions/missing/bookings", json=BOOKING).status_code == 404
    assert partner.delete(PREFIX + "/bookings/missing").status_code == 404


def test_daisy_and_artisia_have_separate_routes():
    from main import app as daisy_app

    daisy_paths = set(daisy_app.openapi()["paths"])
    artisia_paths = set(app.openapi()["paths"])
    assert "/sessions" in daisy_paths
    assert "/v1/sessions" not in daisy_paths
    assert "/v1/sessions" in artisia_paths
    assert "/reservations" not in artisia_paths
