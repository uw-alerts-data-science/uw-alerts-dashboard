"""Tests for the FastAPI backend.

These are DB-free: endpoints that depend on `get_db` override it with a fake
connection and monkeypatch the DB helpers, so the suite runs in CI without a
live Postgres (mirroring `poe test-scraper`).
"""

from unittest.mock import MagicMock

from fastapi.testclient import TestClient

import app.main as main
from app.main import app, get_db

client = TestClient(app)


def _fake_db():
    """Stand-in for get_db: yields a mock connection, never touches Postgres."""
    conn = MagicMock()
    conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (1,)
    yield conn


def test_health():
    app.dependency_overrides[get_db] = _fake_db
    try:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "healthy"}
    finally:
        app.dependency_overrides.clear()


def test_recent_incidents(monkeypatch):
    monkeypatch.setattr(
        main,
        "query_recent_incidents",
        lambda conn, limit=10: [{"id": 1, "category": "Fire"}],
    )
    app.dependency_overrides[get_db] = _fake_db
    try:
        resp = client.get("/query/incidents/recent", params={"limit": 5})
        assert resp.status_code == 200
        assert resp.json() == [{"id": 1, "category": "Fire"}]
    finally:
        app.dependency_overrides.clear()


def test_search_incidents(monkeypatch):
    monkeypatch.setattr(
        main,
        "search_incidents",
        lambda conn, keywords: [{"id": 2, "category": "Robbery"}],
    )
    app.dependency_overrides[get_db] = _fake_db
    try:
        resp = client.get("/query/incidents/search", params={"keywords": "robbery"})
        assert resp.status_code == 200
        assert resp.json() == [{"id": 2, "category": "Robbery"}]
    finally:
        app.dependency_overrides.clear()
