import os

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:5432/test")
# pydantic-settings reads backend/.env by default (cwd when tests run) -- pin this
# explicitly so tests don't silently pick up a real key from a developer's local .env.
os.environ.setdefault("GROQ_API_KEY", "")

import pytest
from app.db import get_db
from app.main import app
from app.rate_limit import reset as reset_rate_limiter
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """The rate limiter's hit-tracking is module-level state -- without this, tests
    that hit /chat/* repeatedly would trip each other's limits depending on run order.
    """
    reset_rate_limiter()
    yield


class FakeResult:
    """Stands in for a SQLAlchemy CursorResult -- enough surface for
    `.mappings().all()` / `.mappings().first()` as used by routers/analytics.py."""

    def __init__(self, rows: list[dict]):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None


class FakeConnection:
    """Queues canned results; each .execute() call returns the next one.

    This is a unit-test double for the DB layer, not an integration test -- it
    verifies route wiring, param validation, and response shape without needing a
    live Postgres. Real query correctness against Postgres-specific SQL (materialized
    views, array_position, etc.) belongs in a separate integration suite run against
    an ephemeral DB in CI (Phase 4), not here.
    """

    def __init__(self, responses: list[list[dict]]):
        self._responses = list(responses)

    def execute(self, _stmt, _params=None):
        if not self._responses:
            raise AssertionError("FakeConnection: no more queued responses")
        return FakeResult(self._responses.pop(0))


@pytest.fixture
def make_client():
    def _make(responses: list[list[dict]]) -> TestClient:
        fake_conn = FakeConnection(responses)

        def fake_get_db():
            yield fake_conn

        app.dependency_overrides[get_db] = fake_get_db
        client = TestClient(app)
        return client

    yield _make
    app.dependency_overrides.clear()


@pytest.fixture
def client(make_client):
    return make_client([])
