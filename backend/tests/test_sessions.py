"""HTTP/service tests with mocked storage and an optional real PostgreSQL test."""

import os
from datetime import datetime
from unittest.mock import MagicMock
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.rows import dict_row

from app.database.init_db import create_tables
from app.repositories import session_repository
from app.services import session_service
from main import app


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


def session_payload():
    return {
        "title": "Tour de potier",
        "starts_at": "2027-01-16T14:00:00+01:00",
        "duration_minutes": 120,
        "capacity": 8,
    }


@pytest.fixture
def session_row():
    return {
        **session_payload(),
        "id": uuid4(),
        "starts_at": datetime.fromisoformat(session_payload()["starts_at"]),
        "booked_seats": 0,
        "sales_state": "open",
    }


@pytest.fixture
def api(monkeypatch, session_row):
    """Keep the real route, validation and service; replace only database access."""
    create_record = MagicMock(return_value=session_row.copy())
    get_record = MagicMock(return_value=session_row.copy())
    monkeypatch.setattr(session_service, "get_connection", MagicMock())
    monkeypatch.setattr(session_repository, "create_session", create_record)
    monkeypatch.setattr(session_repository, "get_session", get_record)
    with TestClient(app) as client:
        yield client, create_record, get_record


def test_create_and_get_serialize_session_and_defaults(api, session_row):
    client, _, _ = api
    response = client.post("/sessions", json=session_payload())
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["id"] == str(session_row["id"])
    assert created["booked_seats"] == 0
    assert created["sales_state"] == "open"
    assert "created_at" not in created
    assert datetime.fromisoformat(created["starts_at"].replace("Z", "+00:00")) == session_row["starts_at"]

    response = client.get(f"/sessions/{created['id']}")
    assert response.status_code == 200, response.text
    assert response.json() == created


@pytest.mark.parametrize("changes", [
    {"title": " \t\n "},
    {"starts_at": "2027-01-16T14:00:00"},
    {"duration_minutes": 0},
    {"duration_minutes": 2_147_483_648},
    {"capacity": -1},
    {"capacity": 2_147_483_648},
    {"capacity": True},
    {"duration_minutes": 1.5},
    {"booked_seats": 3},
])
def test_invalid_creation_is_rejected_before_storage(api, changes):
    client, create_record, _ = api
    response = client.post("/sessions", json={**session_payload(), **changes})
    assert response.status_code == 422, response.text
    create_record.assert_not_called()


def test_missing_required_field_is_rejected(api):
    client, create_record, _ = api
    payload = session_payload()
    del payload["title"]
    assert client.post("/sessions", json=payload).status_code == 422
    create_record.assert_not_called()


def test_invalid_and_missing_session_ids(api):
    client, _, get_record = api
    assert client.get("/sessions/not-a-uuid").status_code == 422
    get_record.assert_not_called()
    get_record.return_value = None
    response = client.get(f"/sessions/{uuid4()}")
    assert response.status_code == 404, response.text
    assert "detail" in response.json()


@pytest.fixture
def postgres_api(monkeypatch):
    schema_name = "daisy_sessions_test_" + uuid4().hex
    with psycopg.connect(TEST_DATABASE_URL) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name)))

    def get_test_connection():
        connection = psycopg.connect(TEST_DATABASE_URL, row_factory=dict_row)
        try:
            connection.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema_name)))
        except Exception:
            connection.close()
            raise
        return connection

    try:
        with get_test_connection() as connection:
            create_tables(connection)
        monkeypatch.setattr(session_service, "get_connection", get_test_connection)
        with TestClient(app) as client:
            yield client, get_test_connection
    finally:
        # Only remove this test's unique schema, never the application's tables.
        with psycopg.connect(TEST_DATABASE_URL) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema_name)))


@pytest.mark.skipif(not TEST_DATABASE_URL, reason="Set TEST_DATABASE_URL to run PostgreSQL tests.")
def test_creation_commits_and_is_readable_on_another_connection(postgres_api):
    client, get_test_connection = postgres_api
    payload = session_payload()
    response = client.post("/sessions", json=payload)
    assert response.status_code == 201, response.text
    created = response.json()
    assert created["booked_seats"] == 0
    assert created["sales_state"] == "open"

    with get_test_connection() as connection:
        row = connection.execute("SELECT * FROM sessions WHERE id = %s", (created["id"],)).fetchone()
    assert row is not None
    assert row["title"] == payload["title"]
    assert row["starts_at"] == datetime.fromisoformat(payload["starts_at"])

    response = client.get(f"/sessions/{created['id']}")
    assert response.status_code == 200, response.text
    assert response.json() == created
