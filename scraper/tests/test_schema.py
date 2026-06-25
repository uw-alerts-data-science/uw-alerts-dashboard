# scraper/tests/test_schema.py
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
    yield conn
    conn.close()


def test_incidents_table_exists(db):
    with db.cursor() as cur:
        cur.execute(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='incidents')"
        )
        assert cur.fetchone()[0] is True


def test_alerts_table_exists(db):
    with db.cursor() as cur:
        cur.execute(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name='alerts')"
        )
        assert cur.fetchone()[0] is True


def test_text_hash_unique_index_exists(db):
    with db.cursor() as cur:
        cur.execute(
            "SELECT indexname FROM pg_indexes WHERE tablename='alerts' AND indexname='idx_alerts_text_hash'"
        )
        assert cur.fetchone() is not None


def test_duplicate_text_hash_rejected(db):
    with db.cursor() as cur:
        cur.execute("DELETE FROM alerts; DELETE FROM incidents;")
        cur.execute(
            "INSERT INTO incidents (category, first_reported_at) VALUES ('Test', NOW()) RETURNING id"
        )
        inc_id = cur.fetchone()[0]
        cur.execute(
            "INSERT INTO alerts (incident_id, alert_type, full_text, text_hash) VALUES (%s, 'original', 'text', 'hash1')",
            (inc_id,),
        )
    db.commit()
    with pytest.raises(psycopg2.errors.UniqueViolation):
        with db.cursor() as cur:
            cur.execute(
                "INSERT INTO alerts (incident_id, alert_type, full_text, text_hash) VALUES (%s, 'original', 'text2', 'hash1')",
                (inc_id,),
            )
        db.commit()
    db.rollback()
