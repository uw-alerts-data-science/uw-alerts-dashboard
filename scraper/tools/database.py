import hashlib
import psycopg2, psycopg2.errors


def query_recent_incidents(conn, limit: int = 10) -> list:
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
                row = cur.fetchone()
                incident_id = row[0] if row is not None else None
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
