import hashlib
import psycopg2, psycopg2.errors


def query_recent_incidents(conn, limit: int = 10) -> list:
    """Return the most recent incidents as a list of dicts.

    Each dict has keys: id, category, nearest_address, first_reported_at
    (ISO string or None), and latest_alert_text (text of the most recent
    alert for that incident).

    Args:
        conn: A psycopg2 connection.
        limit: Maximum number of incidents to return (default 10).
    """
    with conn.cursor() as cur:
        cur.execute("""
            SELECT i.id, i.category, i.nearest_address,
                   i.first_reported_at,
                   (SELECT full_text FROM alerts WHERE incident_id = i.id
                    ORDER BY created_at DESC LIMIT 1) AS latest_text
            FROM incidents i
            ORDER BY i.first_reported_at DESC
            LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
    return [{"id": r[0], "category": r[1], "nearest_address": r[2],
             "first_reported_at": r[3].isoformat() if r[3] else None,
             "latest_alert_text": r[4]} for r in rows]


def upsert_alert(conn, inputs: dict) -> dict:
    """Insert or update an alert and its parent incident.

    When inputs["is_new_incident"] is True, a new row is inserted into
    incidents before the alert row. When False, the existing incident
    (inputs["incident_id"]) has its last_updated_at timestamp refreshed.

    A SHA-256 hash of full_text is stored in alerts.text_hash. If the hash
    already exists (UniqueViolation), the transaction is rolled back and
    {"status": "duplicate", "text_hash": <hash>} is returned.

    Args:
        conn: A psycopg2 connection.
        inputs: Dict with at minimum "full_text", "is_new_incident", and
                "alert_type". New incidents also require "incident_id" to be
                absent; updates require "incident_id".

    Returns:
        {"status": "inserted", "incident_id": int, "alert_id": int}
        or {"status": "duplicate", "text_hash": str}
    """
    full_text = inputs["full_text"]
    text_hash = hashlib.sha256(full_text.encode()).hexdigest()
    is_new = inputs.get("is_new_incident", True)
    try:
        with conn.cursor() as cur:
            if is_new:
                cur.execute("""
                    INSERT INTO incidents
                        (category, nearest_address, google_address, lat, lng,
                         occurred_at, first_reported_at, last_updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,NOW()) RETURNING id
                """, (inputs.get("category"), inputs.get("nearest_address"),
                      inputs.get("google_address"), inputs.get("lat"), inputs.get("lng"),
                      inputs.get("occurred_at"), inputs.get("reported_at")))
                incident_id = (cur.fetchone() or [None])[0]
            else:
                incident_id = inputs["incident_id"]
                cur.execute("UPDATE incidents SET last_updated_at=NOW() WHERE id=%s", (incident_id,))

            cur.execute("""
                INSERT INTO alerts
                    (incident_id, alert_type, reported_at, incident_time,
                     summary, full_text, raw_scraped_text, source_url, text_hash)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
            """, (incident_id, inputs.get("alert_type"), inputs.get("reported_at"),
                  inputs.get("incident_time"), inputs.get("summary"),
                  full_text, inputs.get("raw_scraped_text"),
                  "https://emergency.uw.edu/", text_hash))
            alert_id = cur.fetchone()[0]
        conn.commit()
        return {"status": "inserted", "incident_id": incident_id, "alert_id": alert_id}
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return {"status": "duplicate", "text_hash": text_hash}
