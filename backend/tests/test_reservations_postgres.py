"""Real PostgreSQL checks for idempotency, concurrency and atomic writes."""

import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.rows import dict_row

from app.database.init_db import create_tables
from app.repositories import outbox_repository, reservation_repository
from app.services import reservation_service
from main import app


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="Set TEST_DATABASE_URL to run PostgreSQL tests."
)


@pytest.fixture
def postgres_api(monkeypatch):
    schema_name = "daisy_reservations_test_" + uuid4().hex
    with psycopg.connect(TEST_DATABASE_URL) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema_name)))

    def connect():
        connection = psycopg.connect(TEST_DATABASE_URL, row_factory=dict_row)
        try:
            connection.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema_name)))
            connection.execute("SET statement_timeout = '10s'")
            connection.execute("SET lock_timeout = '5s'")
        except Exception:
            connection.close()
            raise
        return connection

    try:
        with connect() as connection:
            create_tables(connection)
        monkeypatch.setattr(reservation_service, "get_connection", connect)
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, connect
    finally:
        with psycopg.connect(TEST_DATABASE_URL) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema_name)))


def seed_session(connect, capacity=8, booked=0, state="open", partners=("artisia-demo",)):
    with connect() as connection:
        session_id = connection.execute(
            """INSERT INTO sessions
               (title, starts_at, duration_minutes, capacity, booked_seats, sales_state)
               VALUES ('Pottery', '2027-01-16T14:00:00+01:00', 120, %s, %s, %s)
               RETURNING id""",
            (capacity, booked, state),
        ).fetchone()["id"]
        if booked:
            connection.execute(
                """INSERT INTO reservations (session_id, source, source_ref, quantity, status)
                   VALUES (%s, 'artisia-demo', %s, %s, 'confirmed')""",
                (session_id, str(uuid4()), booked),
            )
        for partner in partners:
            connection.execute(
                """INSERT INTO partner_sessions (session_id, partner_id, partner_session_id)
                   VALUES (%s, %s, %s)""",
                (session_id, partner, str(uuid4())),
            )
    return session_id


def book(client, session_id, quantity=2, key="request-1"):
    return client.post(
        "/reservations",
        json={
            "session_id": str(session_id), "quantity": quantity,
            "source": "daisy", "source_ref": key,
        },
    )


def state_of(connect, session_id):
    with connect() as connection:
        return connection.execute(
            """SELECT booked_seats,
                   (SELECT count(*) FROM reservations WHERE session_id = s.id AND source = 'daisy') AS bookings,
                   (SELECT count(*) FROM outbox_events WHERE session_id = s.id) AS tasks,
                   (SELECT coalesce(sum(quantity), 0) FROM reservations
                    WHERE session_id = s.id AND status = 'confirmed') AS confirmed_seats
               FROM sessions s WHERE id = %s""",
            (session_id,),
        ).fetchone()


def test_booking_and_replay_enqueue_once_per_partner(postgres_api):
    client, connect = postgres_api
    session_id = seed_session(connect, partners=("artisia-demo", "partner-two"))
    first = book(client, session_id)
    assert first.status_code == 201, first.text
    replay = book(client, session_id)
    assert replay.status_code == 200, replay.text
    assert replay.json() == first.json()
    assert state_of(connect, session_id) == {
        "booked_seats": 2, "bookings": 1, "tasks": 2, "confirmed_seats": 2,
    }
    with connect() as connection:
        tasks = connection.execute("SELECT partner_id, partner_session_id, status FROM outbox_events").fetchall()
        mappings = connection.execute("SELECT partner_id, partner_session_id FROM partner_sessions").fetchall()
    assert {(task["partner_id"], task["partner_session_id"]) for task in tasks} == {
        (mapping["partner_id"], mapping["partner_session_id"]) for mapping in mappings
    }
    assert {(task["partner_id"], task["status"]) for task in tasks} == {
        ("artisia-demo", "pending"), ("partner-two", "pending"),
    }


def test_same_key_with_different_parameters_conflicts(postgres_api):
    client, connect = postgres_api
    first_id = seed_session(connect)
    second_id = seed_session(connect)
    assert book(client, first_id).status_code == 201
    before = state_of(connect, first_id)
    assert book(client, first_id, quantity=3).status_code == 409
    assert book(client, second_id).status_code == 409
    assert state_of(connect, first_id) == before
    assert state_of(connect, second_id)["booked_seats"] == 0


@pytest.mark.parametrize("capacity,booked,state,quantity", [
    (1, 1, "open", 1),
    (8, 0, "paused", 1),
    (8, 0, "cancelled", 1),
    (1, 2, "open", 1),
    (2_147_483_647, 1, "open", 2_147_483_647),
])
def test_unavailable_booking_rolls_back_new_reservation(postgres_api, capacity, booked, state, quantity):
    client, connect = postgres_api
    session_id = seed_session(connect, capacity, booked, state)
    before = state_of(connect, session_id)
    response = book(client, session_id, quantity=quantity)
    assert response.status_code == 409, response.text
    assert state_of(connect, session_id) == before


def test_failed_request_does_not_consume_key(postgres_api):
    client, connect = postgres_api
    session_id = seed_session(connect, capacity=1)
    assert book(client, session_id, quantity=2).status_code == 409
    assert book(client, session_id, quantity=1).status_code == 201
    assert state_of(connect, session_id)["booked_seats"] == 1


def test_missing_session_is_404(postgres_api):
    client, _ = postgres_api
    assert book(client, uuid4()).status_code == 404


def test_session_without_partner_has_no_outbox_tasks(postgres_api):
    client, connect = postgres_api
    session_id = seed_session(connect, partners=())
    assert book(client, session_id).status_code == 201
    assert state_of(connect, session_id) == {
        "booked_seats": 2, "bookings": 1, "tasks": 0, "confirmed_seats": 2,
    }


def test_retry_after_cancellation_does_not_reactivate_booking(postgres_api):
    client, connect = postgres_api
    session_id = seed_session(connect)
    first = book(client, session_id)
    assert first.status_code == 201
    with connect() as connection:
        connection.execute(
            "UPDATE reservations SET status = 'cancelled', updated_at = now() WHERE id = %s",
            (first.json()["id"],),
        )
        connection.execute("UPDATE sessions SET booked_seats = 0 WHERE id = %s", (session_id,))
    before = state_of(connect, session_id)
    replay = book(client, session_id)
    assert replay.status_code == 200
    assert replay.json()["status"] == "cancelled"
    assert state_of(connect, session_id) == before


def test_outbox_failure_rolls_back_all_writes(postgres_api, monkeypatch):
    client, connect = postgres_api
    session_id = seed_session(connect)
    original = outbox_repository.create_outbox_event

    def fail_after_insert(connection, session_id):
        original(connection, session_id)
        raise RuntimeError("Simulated failure before transaction commit")

    monkeypatch.setattr(outbox_repository, "create_outbox_event", fail_after_insert)
    assert book(client, session_id).status_code == 500
    assert state_of(connect, session_id) == {
        "booked_seats": 0, "bookings": 0, "tasks": 0, "confirmed_seats": 0,
    }
    monkeypatch.setattr(outbox_repository, "create_outbox_event", original)
    assert book(client, session_id).status_code == 201


@pytest.mark.parametrize("same_key,expected_codes", [(False, [201, 409]), (True, [200, 201])])
def test_concurrent_last_seat(postgres_api, monkeypatch, same_key, expected_codes):
    _, connect = postgres_api
    session_id = seed_session(connect, capacity=1)
    barrier = Barrier(2, timeout=5)
    original = reservation_repository.create_reservation

    def synchronized_insert(connection, session_id, quantity, source, source_ref):
        if same_key:
            barrier.wait()
        reservation = original(connection, session_id, quantity, source, source_ref)
        if not same_key:
            # Both transactions have inserted their identities before trying
            # to claim the single remaining seat.
            barrier.wait()
        return reservation

    monkeypatch.setattr(reservation_repository, "create_reservation", synchronized_insert)

    def send(key):
        with TestClient(app, raise_server_exceptions=False) as client:
            return book(client, session_id, quantity=1, key=key)

    keys = ["same", "same"] if same_key else ["first", "second"]
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(send, keys))
    assert sorted(response.status_code for response in responses) == expected_codes, [r.text for r in responses]
    if same_key:
        assert responses[0].json()["id"] == responses[1].json()["id"]
    assert state_of(connect, session_id) == {
        "booked_seats": 1, "bookings": 1, "tasks": 1, "confirmed_seats": 1,
    }


def test_worker_uses_partner_session_id_saved_in_outbox(postgres_api, monkeypatch):
    import httpx
    from app import worker

    client, connect = postgres_api
    session_id = seed_session(connect)
    assert book(client, session_id).status_code == 201
    with connect() as connection:
        task = connection.execute("SELECT * FROM outbox_events").fetchone()
        connection.execute(
            "UPDATE partner_sessions SET partner_session_id = 'changed-later' WHERE session_id = %s",
            (session_id,),
        )

    requests = []
    def respond(url, **kwargs):
        requests.append((url, kwargs))
        return httpx.Response(
            200, json={"capacity": 6, "booked": 0, "status": "published"},
            request=httpx.Request("PATCH", url),
        )

    monkeypatch.setattr(worker, "get_connection", connect)
    monkeypatch.setattr(worker.httpx, "patch", respond)
    monkeypatch.setenv("ARTISIA_BASE_URL", "http://artisia.test/v1")
    worker.process_one_outbox(task)

    assert requests[0][0].endswith("/sessions/" + task["partner_session_id"])
    assert requests[0][1]["json"] == {"capacity": 6, "status": "published"}
    with connect() as connection:
        assert connection.execute("SELECT status FROM outbox_events").fetchone()["status"] == "processed"


def test_get_pending_events_returns_at_most_ten_in_order(postgres_api):
    _, connect = postgres_api
    session_id = seed_session(connect, partners=("artisia-demo", "partner-two"))
    with connect() as connection:
        for _ in range(12):
            outbox_repository.create_outbox_event(connection, session_id)
        events = outbox_repository.get_pending_events(connection, "artisia-demo")
        expected = connection.execute(
            "SELECT id FROM outbox_events WHERE partner_id = 'artisia-demo' ORDER BY id LIMIT 10"
        ).fetchall()
        assert len(events) == 10
        assert [event["id"] for event in events] == [row["id"] for row in expected]
        assert all(event["status"] == "pending" and event["partner_id"] == "artisia-demo"
                   for event in events)
        connection.execute("UPDATE outbox_events SET status = 'blocked' WHERE partner_id = 'artisia-demo'")
        assert outbox_repository.get_pending_events(connection, "artisia-demo") == []


def test_worker_calls_independent_artisia_app_over_real_http(postgres_api, monkeypatch, tmp_path):
    import socket
    import subprocess
    import sys
    import time
    from pathlib import Path
    import httpx
    from app import worker

    client, connect = postgres_api
    session_id = seed_session(connect, partners=("artisia",))
    with connect() as connection:
        connection.execute(
            "UPDATE partner_sessions SET partner_session_id = 'art_ses_8812' WHERE session_id = %s",
            (session_id,),
        )
    assert book(client, session_id).status_code == 201
    with connect() as connection:
        task = connection.execute("SELECT * FROM outbox_events").fetchone()

    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base_url = f"http://127.0.0.1:{port}/v1"
    api_key = "integration-key"
    env = {
        **os.environ,
        "ARTISIA_API_KEY": api_key,
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    env.pop("DATABASE_URL", None)
    env.pop("TEST_DATABASE_URL", None)
    with (tmp_path / "api.log").open("wb") as output:
        process = subprocess.Popen(
            [sys.executable, "-B", "-m", "uvicorn", "artisia_app.main:app", "--host", "127.0.0.1",
             "--port", str(port), "--log-level", "warning", "--no-access-log"],
            cwd=Path(__file__).resolve().parents[1], env=env,
            stdout=output, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            with httpx.Client(headers={"Authorization": "Bearer " + api_key}, timeout=2) as partner:
                deadline = time.monotonic() + 10
                while True:
                    assert process.poll() is None, "API stopped before it was ready"
                    try:
                        response = partner.get(base_url + "/sessions")
                        if response.status_code == 200:
                            break
                    except httpx.RequestError:
                        pass
                    assert time.monotonic() < deadline, "API did not start"
                    time.sleep(0.05)

                monkeypatch.setattr(worker, "get_connection", connect)
                monkeypatch.setenv("ARTISIA_BASE_URL", base_url)
                monkeypatch.setenv("ARTISIA_API_KEY", api_key)
                worker.process_one_outbox(task)

                session = partner.get(base_url + "/sessions").json()["sessions"][0]
                assert (session["capacity"], session["booked"]) == (6, 0)
                booking = partner.post(base_url + "/sessions/art_ses_8812/bookings", json={
                    "customer": {"name": "Camille", "email": "camille@example.com"},
                    "seats": 1, "external_ref": "integration-booking",
                })
                assert booking.status_code == 201
                assert partner.get(base_url + "/sessions").json()["sessions"][0]["booked"] == 1
                assert partner.delete(base_url + "/bookings/" + booking.json()["booking_id"]).status_code == 204
                assert partner.get(base_url + "/sessions").json()["sessions"][0]["booked"] == 0

            with connect() as connection:
                assert connection.execute("SELECT status FROM outbox_events").fetchone()["status"] == "processed"
                mapping = connection.execute("SELECT observed_capacity, last_pushed_at FROM partner_sessions").fetchone()
                assert mapping["observed_capacity"] == 6 and mapping["last_pushed_at"] is not None
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
