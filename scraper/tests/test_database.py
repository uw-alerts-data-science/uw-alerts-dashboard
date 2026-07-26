# scraper/tests/test_database.py
import hashlib
from unittest.mock import MagicMock
import psycopg2
import pytest
from pydantic import ValidationError


def mock_conn(fetchall=None, fetchone=None):
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    cur.fetchall.return_value = fetchall or []
    cur.fetchone.return_value = fetchone
    return conn, cur


def test_query_returns_list_of_dicts():
    conn, cur = mock_conn(fetchall=[(1, "Stabbing", "Padelford", None, "UPDATE text")])
    cur.fetchall.return_value = [(1, "Stabbing", "Padelford", None, "UPDATE text")]
    from scraper.tools.database import query_recent_incidents

    result = query_recent_incidents(conn, limit=5)
    assert isinstance(result, list)
    assert result[0]["id"] == 1
    assert result[0]["category"] == "Stabbing"


def test_upsert_new_incident_inserts_incident_and_alert():
    conn, cur = mock_conn(fetchone=(42,))
    from scraper.tools.database import upsert_alert

    result = upsert_alert(
        conn,
        {
            "is_new_incident": True,
            "alert_type": "original",
            "full_text": "Test alert",
            "raw_scraped_text": "Test alert",
            "category": "Theft",
            "nearest_address": "HUB",
        },
    )
    assert result["status"] == "inserted"
    assert result["incident_id"] == 42
    calls_str = str(cur.execute.call_args_list)
    assert "INSERT INTO incidents" in calls_str
    assert "INSERT INTO alerts" in calls_str


def test_upsert_update_skips_incident_insert():
    conn, cur = mock_conn(fetchone=(99,))
    from scraper.tools.database import upsert_alert

    upsert_alert(
        conn,
        {
            "is_new_incident": False,
            "incident_id": 5,
            "alert_type": "update",
            "full_text": "UPDATE: still investigating",
            "raw_scraped_text": "UPDATE: still investigating",
        },
    )
    calls_str = str(cur.execute.call_args_list)
    assert "INSERT INTO incidents" not in calls_str
    assert "last_updated_at" in calls_str


def test_upsert_update_coalesces_provided_fields():
    conn, cur = mock_conn(fetchone=(99,))
    from scraper.tools.database import upsert_alert

    upsert_alert(
        conn,
        {
            "is_new_incident": False,
            "incident_id": 5,
            "alert_type": "update",
            "full_text": "UPDATE: confirmed as a robbery near HUB Lawn.",
            "raw_scraped_text": "UPDATE: confirmed as a robbery near HUB Lawn.",
            "category": "Robbery",
            "nearest_address": "HUB Lawn",
            "lat": 47.6553,
            "lng": -122.3035,
        },
    )
    calls_str = str(cur.execute.call_args_list)
    assert "COALESCE" in calls_str
    assert "'Robbery'" in calls_str
    assert "HUB Lawn" in calls_str
    assert "47.6553" in calls_str


def test_upsert_update_with_no_fields_leaves_params_null():
    conn, cur = mock_conn(fetchone=(99,))
    from scraper.tools.database import upsert_alert

    upsert_alert(
        conn,
        {
            "is_new_incident": False,
            "incident_id": 5,
            "alert_type": "update",
            "full_text": "UPDATE: still investigating",
            "raw_scraped_text": "UPDATE: still investigating",
        },
    )
    incidents_update_call = cur.execute.call_args_list[0]
    params = incidents_update_call.args[1]
    assert params == (None, None, None, None, None, None, 5)


def test_known_source_urls_returns_subset_present_in_db():
    conn, cur = mock_conn(fetchall=[("https://emergency.uw.edu/known/",)])
    from scraper.tools.database import known_source_urls

    result = known_source_urls(
        conn, ["https://emergency.uw.edu/known/", "https://emergency.uw.edu/new/"]
    )
    assert result == {"https://emergency.uw.edu/known/"}


def test_known_source_urls_empty_input_returns_empty_set_without_query():
    conn, cur = mock_conn()
    from scraper.tools.database import known_source_urls

    result = known_source_urls(conn, [])
    assert result == set()
    cur.execute.assert_not_called()


def test_find_incident_id_by_source_url_returns_id_when_known():
    conn, cur = mock_conn(fetchone=(42,))
    from scraper.tools.database import find_incident_id_by_source_url

    result = find_incident_id_by_source_url(conn, "https://emergency.uw.edu/known/")
    assert result == 42


def test_find_incident_id_by_source_url_returns_none_when_unknown():
    conn, cur = mock_conn(fetchone=None)
    from scraper.tools.database import find_incident_id_by_source_url

    result = find_incident_id_by_source_url(conn, "https://emergency.uw.edu/new/")
    assert result is None


def test_get_last_scraped_hash_returns_hash_when_recorded():
    conn, cur = mock_conn(fetchone=("a" * 64,))
    from scraper.tools.database import get_last_scraped_hash

    result = get_last_scraped_hash(conn, 42)
    assert result == "a" * 64


def test_get_last_scraped_hash_returns_none_when_never_recorded():
    conn, cur = mock_conn(fetchone=(None,))
    from scraper.tools.database import get_last_scraped_hash

    result = get_last_scraped_hash(conn, 42)
    assert result is None


def test_record_scrape_hash_updates_incident_and_commits():
    conn, cur = mock_conn()
    from scraper.tools.database import record_scrape_hash

    record_scrape_hash(conn, 42, "b" * 64)
    calls_str = str(cur.execute.call_args_list)
    assert "UPDATE incidents SET last_scraped_hash" in calls_str
    assert ("b" * 64, 42) in [c.args[1] for c in cur.execute.call_args_list]
    conn.commit.assert_called_once()


def test_upsert_computes_correct_text_hash():
    conn, cur = mock_conn(fetchone=(77,))
    from scraper.tools.database import upsert_alert

    text = "ORIGINAL POST: Armed suspect near Drumheller."
    upsert_alert(
        conn,
        {
            "is_new_incident": True,
            "alert_type": "original",
            "full_text": text,
            "raw_scraped_text": text,
        },
    )
    expected_hash = hashlib.sha256(text.encode()).hexdigest()
    assert expected_hash in str(cur.execute.call_args_list)


def test_upsert_unknown_category_coerced_to_other_in_db():
    conn, cur = mock_conn(fetchone=(50,))
    from scraper.tools.database import upsert_alert

    upsert_alert(
        conn,
        {
            "is_new_incident": True,
            "alert_type": "original",
            "full_text": "Report of a stabbing near the HUB.",
            "raw_scraped_text": "Report of a stabbing near the HUB.",
            "category": "Stabbing",  # not a real category — must coerce, not pass through
        },
    )
    calls_str = str(cur.execute.call_args_list)
    assert "'Other'" in calls_str
    assert "Stabbing" not in calls_str


def test_upsert_missing_full_text_raises_before_touching_db():
    conn, cur = mock_conn()
    from scraper.tools.database import upsert_alert

    with pytest.raises(ValidationError):
        upsert_alert(
            conn,
            {
                "is_new_incident": True,
                "alert_type": "original",
                "raw_scraped_text": "text",
            },
        )
    cur.execute.assert_not_called()


def test_upsert_duplicate_hash_returns_duplicate_status():
    conn, cur = mock_conn()
    cur.execute.side_effect = [None, psycopg2.errors.UniqueViolation("dup")]
    conn.rollback = MagicMock()
    from scraper.tools.database import upsert_alert

    result = upsert_alert(
        conn,
        {
            "is_new_incident": True,
            "alert_type": "original",
            "full_text": "dupe text",
            "raw_scraped_text": "dupe text",
        },
    )
    assert result["status"] == "duplicate"
    conn.rollback.assert_called_once()
