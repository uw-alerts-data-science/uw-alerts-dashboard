import hashlib
import psycopg2
import psycopg2.errors

from scraper.db.models import AlertType, IncidentCategory, UpsertAlertInput

QUERY_RECENT_INCIDENTS_SCHEMA = {
    "name": "query_recent_incidents",
    "description": "Get N most recent incidents from DB to detect duplicates and match updates.",
    "input_schema": {
        "type": "object",
        "properties": {"limit": {"type": "integer", "default": 10}},
        "required": [],
    },
}

_UPSERT_ALERT_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "is_new_incident": {"type": "boolean"},
        "incident_id": {"type": "integer"},
        "alert_type": {"type": "string", "enum": [t.value for t in AlertType]},
        "category": {"type": "string", "enum": [c.value for c in IncidentCategory]},
        "nearest_address": {"type": "string"},
        "google_address": {"type": "string"},
        "lat": {"type": "number"},
        "lng": {"type": "number"},
        "occurred_at": {"type": "string"},
        "reported_at": {"type": "string"},
        "incident_time": {"type": "string"},
        "summary": {"type": "string"},
        "full_text": {"type": "string"},
        "raw_scraped_text": {"type": "string"},
        "source_url": {"type": "string"},
    },
    "required": ["is_new_incident", "alert_type", "full_text", "raw_scraped_text"],
}


def build_upsert_alert_schema(description: str) -> dict:
    """Build the upsert_alert tool schema with a caller-specific description.

    The input shape (and its category/alert_type enums) is shared so the two
    callers can never drift out of sync; only the guidance text differs.
    """
    return {
        "name": "upsert_alert",
        "description": description,
        "input_schema": _UPSERT_ALERT_INPUT_SCHEMA,
    }


def query_recent_incidents(conn, limit: int = 10) -> list:
    """Return the most recent incidents as a list of dicts.

    Each dict has keys: id, category, nearest_address, first_reported_at
    (ISO string or None), and latest_alert_text (text of the most recent
    alert for that incident).

    Args:
        conn: A psycopg2 connection.
        limit: Maximum number of incidents to return (default 10).
    """
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT i.id, i.category, i.nearest_address,
                       i.first_reported_at,
                       (SELECT full_text FROM alerts WHERE incident_id = i.id
                        ORDER BY created_at DESC LIMIT 1) AS latest_text
                FROM incidents i
                ORDER BY COALESCE(i.first_reported_at, i.created_at) DESC
                LIMIT %s
            """,
                (limit,),
            )
            rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "category": r[1],
                "nearest_address": r[2],
                "first_reported_at": r[3].isoformat() if r[3] else None,
                "latest_alert_text": r[4],
            }
            for r in rows
        ]
    except psycopg2.Error:
        conn.rollback()
        raise


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
    validated = UpsertAlertInput(**inputs)
    full_text = validated.full_text
    text_hash = hashlib.sha256(full_text.encode()).hexdigest()
    is_new = validated.is_new_incident
    try:
        with conn.cursor() as cur:
            if is_new:
                cur.execute(
                    """
                    INSERT INTO incidents
                        (category, nearest_address, google_address, lat, lng,
                         occurred_at, first_reported_at, last_updated_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,NOW()) RETURNING id
                """,
                    (
                        validated.category.value if validated.category else None,
                        validated.nearest_address,
                        validated.google_address,
                        validated.lat,
                        validated.lng,
                        validated.occurred_at,
                        validated.reported_at,
                    ),
                )
                incident_id = (cur.fetchone() or [None])[0]
            else:
                incident_id = validated.incident_id
                cur.execute(
                    "UPDATE incidents SET last_updated_at=NOW() WHERE id=%s",
                    (incident_id,),
                )

            cur.execute(
                """
                INSERT INTO alerts
                    (incident_id, alert_type, reported_at, incident_time,
                     summary, full_text, raw_scraped_text, source_url, text_hash)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
            """,
                (
                    incident_id,
                    validated.alert_type.value,
                    validated.reported_at,
                    validated.incident_time,
                    validated.summary,
                    full_text,
                    validated.raw_scraped_text,
                    validated.source_url or "https://emergency.uw.edu/",
                    text_hash,
                ),
            )
            alert_id = cur.fetchone()[0]
        conn.commit()
        return {"status": "inserted", "incident_id": incident_id, "alert_id": alert_id}
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        return {"status": "duplicate", "text_hash": text_hash}


def search_incidents(conn, keywords: str, limit: int = 5) -> list:
    """Search incidents by keyword across address, category, and alert text.

    Useful for finding a parent incident when linking update alerts during
    historical batch import. Returns results ordered newest-first.

    Args:
        conn: A psycopg2 connection.
        keywords: Search string matched case-insensitively against nearest_address,
                  category, and the full_text of any associated alert.
        limit: Maximum number of results (default 5).

    Returns:
        List of dicts with keys: id, category, nearest_address,
        first_reported_at (ISO string or None), first_alert_text.
    """
    pattern = f"%{keywords}%"
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT i.id, i.category, i.nearest_address,
                       i.first_reported_at,
                       (SELECT full_text FROM alerts
                        WHERE incident_id = i.id
                        ORDER BY created_at ASC LIMIT 1) AS first_alert_text
                FROM incidents i
                WHERE i.nearest_address ILIKE %s
                   OR i.category ILIKE %s
                   OR EXISTS (
                       SELECT 1 FROM alerts a
                       WHERE a.incident_id = i.id AND a.full_text ILIKE %s
                   )
                ORDER BY i.first_reported_at DESC
                LIMIT %s
            """,
                (pattern, pattern, pattern, limit),
            )
            rows = cur.fetchall()
        return [
            {
                "id": r[0],
                "category": r[1],
                "nearest_address": r[2],
                "first_reported_at": r[3].isoformat() if r[3] else None,
                "first_alert_text": r[4],
            }
            for r in rows
        ]
    except psycopg2.Error:
        conn.rollback()
        raise
