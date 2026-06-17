# scraper/tests/test_database.py
import hashlib, pytest
from unittest.mock import MagicMock, patch
import psycopg2

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
    result = upsert_alert(conn, {
        "is_new_incident": True, "alert_type": "original",
        "full_text": "Test alert", "raw_scraped_text": "Test alert",
        "category": "Theft", "nearest_address": "HUB",
    })
    assert result["status"] == "inserted"
    assert result["incident_id"] == 42
    calls_str = str(cur.execute.call_args_list)
    assert "INSERT INTO incidents" in calls_str
    assert "INSERT INTO alerts" in calls_str

def test_upsert_update_skips_incident_insert():
    conn, cur = mock_conn(fetchone=(99,))
    from scraper.tools.database import upsert_alert
    upsert_alert(conn, {
        "is_new_incident": False, "incident_id": 5,
        "alert_type": "update",
        "full_text": "UPDATE: still investigating", "raw_scraped_text": "UPDATE: still investigating",
    })
    calls_str = str(cur.execute.call_args_list)
    assert "INSERT INTO incidents" not in calls_str
    assert "last_updated_at" in calls_str

def test_upsert_computes_correct_text_hash():
    conn, cur = mock_conn(fetchone=(77,))
    from scraper.tools.database import upsert_alert
    text = "ORIGINAL POST: Armed suspect near Drumheller."
    upsert_alert(conn, {"is_new_incident": True, "alert_type": "original",
                        "full_text": text, "raw_scraped_text": text})
    expected_hash = hashlib.sha256(text.encode()).hexdigest()
    assert expected_hash in str(cur.execute.call_args_list)

def test_upsert_duplicate_hash_returns_duplicate_status():
    conn, cur = mock_conn()
    cur.execute.side_effect = [None, psycopg2.errors.UniqueViolation("dup")]
    conn.rollback = MagicMock()
    from scraper.tools.database import upsert_alert
    result = upsert_alert(conn, {"is_new_incident": True, "alert_type": "original",
                                  "full_text": "dupe text", "raw_scraped_text": "dupe text"})
    assert result["status"] == "duplicate"
    conn.rollback.assert_called_once()
