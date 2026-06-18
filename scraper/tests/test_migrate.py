# scraper/tests/test_migrate.py
import os
import pytest
import psycopg2


@pytest.fixture(scope="module")
def db():
    url = os.environ.get("TEST_DATABASE_URL", "postgres://localhost/uw_alerts_test")
    sep = "&" if "?" in url else "?"
    try:
        conn = psycopg2.connect(url + sep + "connect_timeout=3")
    except psycopg2.OperationalError as e:
        pytest.skip(f"test DB unavailable: {e}")
    with conn.cursor() as cur:
        cur.execute("DELETE FROM alerts; DELETE FROM incidents;")
    conn.commit()
    yield conn
    conn.close()


def test_migrate_inserts_expected_counts(db):
    from scraper.db.migrate import migrate_csv

    result = migrate_csv("data/uw_alerts_clean.csv", db)
    assert result["incidents_inserted"] == 98
    assert result["alerts_inserted"] == 285
    assert result["duplicates_skipped"] == 0


def test_migrate_is_idempotent(db):
    from scraper.db.migrate import migrate_csv

    result = migrate_csv("data/uw_alerts_clean.csv", db)
    assert result["alerts_inserted"] == 0
    assert result["duplicates_skipped"] == 285
