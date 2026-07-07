"""
Unit tests for the FastAPI app.

These run WITHOUT AWS and WITHOUT a real database. The database layer
(`get_connection`) is replaced with an in-memory fake so we can test the
request/response behaviour and validation logic in isolation.

Run: pytest app/tests -q
"""

import os
from contextlib import contextmanager

# Ensure startup DB init is skipped when the app module is imported.
os.environ["SKIP_DB_INIT"] = "1"

import pytest
from fastapi.testclient import TestClient

import main


# ---------------------------------------------------------------------------
# In-memory fake database
# ---------------------------------------------------------------------------
class FakeCursor:
    """Minimal cursor emulating just what the app uses."""

    def __init__(self, store):
        self._store = store
        self._result = None

    def execute(self, query, params=None):
        q = " ".join(query.split()).lower()  # normalise whitespace
        if q.startswith("create table"):
            self._result = None
        elif q.startswith("select id, name from items"):
            self._result = [(i["id"], i["name"]) for i in self._store["items"]]
        elif q.startswith("insert into items"):
            new_id = self._store["next_id"]
            self._store["next_id"] += 1
            self._store["items"].append({"id": new_id, "name": params[0]})
            self._result = [(new_id,)]
        else:
            self._result = None

    def fetchall(self):
        return list(self._result or [])

    def fetchone(self):
        return self._result[0] if self._result else None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeConnection:
    def __init__(self, store):
        self._store = store

    def cursor(self):
        return FakeCursor(self._store)

    def commit(self):
        pass

    def close(self):
        pass


@pytest.fixture
def client(monkeypatch):
    """TestClient with the DB layer swapped for an in-memory fake."""
    store = {"items": [], "next_id": 1}

    @contextmanager
    def fake_get_connection():
        yield FakeConnection(store)

    monkeypatch.setattr(main, "get_connection", fake_get_connection)
    return TestClient(main.app)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_health_returns_200_and_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_health_does_not_touch_db(monkeypatch):
    """/health must not open a DB connection (it's a liveness probe)."""

    def explode():
        raise AssertionError("health must not call the database")

    monkeypatch.setattr(main, "get_connection", explode)
    client = TestClient(main.app)
    resp = client.get("/health")
    assert resp.status_code == 200


def test_list_items_empty(client):
    resp = client.get("/items")
    assert resp.status_code == 200
    assert resp.json() == []


def test_create_then_list_item(client):
    create = client.post("/items", json={"name": "widget"})
    assert create.status_code == 201
    body = create.json()
    assert body["name"] == "widget"
    assert isinstance(body["id"], int)

    listing = client.get("/items")
    assert listing.status_code == 200
    names = [i["name"] for i in listing.json()]
    assert "widget" in names


def test_create_item_rejects_empty_name(client):
    resp = client.post("/items", json={"name": ""})
    assert resp.status_code == 422  # pydantic validation error


def test_create_item_rejects_missing_name(client):
    resp = client.post("/items", json={})
    assert resp.status_code == 422


def test_create_item_rejects_too_long_name(client):
    resp = client.post("/items", json={"name": "x" * 256})
    assert resp.status_code == 422


def test_ids_increment_across_inserts(client):
    first = client.post("/items", json={"name": "a"}).json()
    second = client.post("/items", json={"name": "b"}).json()
    assert second["id"] == first["id"] + 1
