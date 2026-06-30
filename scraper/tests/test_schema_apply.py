import os

import psycopg2
import pytest


@pytest.fixture(scope="module")
def test_db():
    url = os.environ.get("TEST_DATABASE_URL", "postgres://localhost/uw_alerts_test")
    sep = "&" if "?" in url else "?"
    try:
        conn = psycopg2.connect(url + sep + "connect_timeout=3")
    except psycopg2.OperationalError as e:
        pytest.skip(f"test DB unavailable: {e}")
    # Start with a clean slate
    with conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS alerts CASCADE")
            cur.execute("DROP TABLE IF EXISTS incidents CASCADE")
    yield conn
    conn.close()


def test_apply_schema_creates_tables(test_db):
    from scraper.db.schema import apply_schema
    apply_schema(url=os.environ.get("TEST_DATABASE_URL", "postgres://localhost/uw_alerts_test"))
    with test_db.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_name IN ('incidents', 'alerts') ORDER BY table_name"
        )
        tables = [row[0] for row in cur.fetchall()]
    assert tables == ["alerts", "incidents"]


def test_apply_schema_is_idempotent(test_db):
    from scraper.db.schema import apply_schema
    url = os.environ.get("TEST_DATABASE_URL", "postgres://localhost/uw_alerts_test")
    # Second call must not raise
    apply_schema(url=url)
