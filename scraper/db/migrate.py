import ast
import hashlib
import pandas as pd
import psycopg2
import psycopg2.errors


def migrate_csv(csv_path: str, conn) -> dict:
    df = pd.read_csv(csv_path, converters={"geometry": ast.literal_eval})
    df = df.where(pd.notnull(df), None)

    incidents_inserted = 0
    alerts_inserted = 0
    duplicates_skipped = 0
    incident_id_map = {}

    for inc_id_csv, group in df.groupby("Incident ID"):
        first = group.iloc[0]
        geo = first["geometry"]
        lat = geo["location"]["lat"] if geo else None
        lng = geo["location"]["lng"] if geo else None
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO incidents (category, nearest_address, google_address,
                    lat, lng, first_reported_at, last_updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id
            """,
                (
                    first.get("Incident Category"),
                    first.get("Nearest Address to Incident"),
                    first.get("Google Address"),
                    lat,
                    lng,
                    pd.to_datetime(str(first["Date"])).isoformat()
                    if first.get("Date")
                    else None,
                    pd.to_datetime(str(group.iloc[-1]["Date"])).isoformat()
                    if first.get("Date")
                    else None,
                ),
            )
            incident_id_map[inc_id_csv] = cur.fetchone()[0]
        conn.commit()
        incidents_inserted += 1

    for _, row in df.iterrows():
        full_text = str(row.get("Incident Alert") or "")
        text_hash = hashlib.sha256(full_text.encode()).hexdigest()
        inc_db_id = incident_id_map.get(row["Incident ID"])
        try:
            with conn.cursor() as cur:
                reported = None
                if row.get("Date") and row.get("Report Time"):
                    try:
                        reported = pd.to_datetime(
                            f"{row['Date']} {row['Report Time']}"
                        ).isoformat()
                    except Exception:
                        pass
                cur.execute(
                    """
                    INSERT INTO alerts (incident_id, alert_type, reported_at,
                        summary, full_text, raw_scraped_text, source_url, text_hash)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                    (
                        inc_db_id,
                        str(row.get("Alert Type") or "original").lower(),
                        reported,
                        row.get("Incident Summary"),
                        full_text,
                        full_text,
                        "https://emergency.uw.edu/",
                        text_hash,
                    ),
                )
            conn.commit()
            alerts_inserted += 1
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            duplicates_skipped += 1

    return {
        "incidents_inserted": incidents_inserted,
        "alerts_inserted": alerts_inserted,
        "duplicates_skipped": duplicates_skipped,
    }


def seed_if_empty(snapshot_dir: str, conn) -> dict:
    """Seed from snapshot only if the incidents table is empty. Safe to re-run."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM incidents")
        count = cur.fetchone()[0]
    if count > 0:
        print(f"Database already contains {count} incident(s) — skipping seed.")
        return {"incidents_inserted": 0, "alerts_inserted": 0, "duplicates_skipped": count}
    return seed_from_snapshot(snapshot_dir, conn)


def seed_from_snapshot(snapshot_dir: str, conn) -> dict:
    """Seed the DB from CSV files produced by dump_to_csv.

    Designed for seeding a fresh database. Alerts are idempotent via
    text_hash uniqueness; incidents have no natural unique key so running
    this against a non-empty DB will produce duplicate incidents.
    """
    import os

    incidents_path = os.path.join(snapshot_dir, "incidents.csv")
    alerts_path = os.path.join(snapshot_dir, "alerts.csv")

    incidents_df = pd.read_csv(incidents_path)
    incidents_df = incidents_df.where(pd.notnull(incidents_df), None)

    alerts_df = pd.read_csv(alerts_path)
    alerts_df = alerts_df.where(pd.notnull(alerts_df), None)

    incidents_inserted = 0
    alerts_inserted = 0
    duplicates_skipped = 0
    id_map = {}

    incident_cols = [
        "category", "nearest_address", "google_address", "lat", "lng",
        "occurred_at", "first_reported_at", "last_updated_at",
    ]
    for _, row in incidents_df.iterrows():
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO incidents ({', '.join(incident_cols)})
                VALUES ({', '.join(['%s'] * len(incident_cols))})
                RETURNING id
                """,
                tuple(row.get(c) for c in incident_cols),
            )
            id_map[int(row["id"])] = cur.fetchone()[0]
        conn.commit()
        incidents_inserted += 1

    alert_cols = [
        "incident_id", "alert_type", "reported_at", "incident_time",
        "summary", "full_text", "raw_scraped_text", "source_url", "text_hash",
    ]
    for _, row in alerts_df.iterrows():
        mapped_incident_id = id_map.get(int(row["incident_id"]))
        if mapped_incident_id is None:
            continue
        try:
            with conn.cursor() as cur:
                values = [
                    mapped_incident_id if c == "incident_id" else row.get(c)
                    for c in alert_cols
                ]
                cur.execute(
                    f"""
                    INSERT INTO alerts ({', '.join(alert_cols)})
                    VALUES ({', '.join(['%s'] * len(alert_cols))})
                    """,
                    tuple(values),
                )
            conn.commit()
            alerts_inserted += 1
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            duplicates_skipped += 1

    return {
        "incidents_inserted": incidents_inserted,
        "alerts_inserted": alerts_inserted,
        "duplicates_skipped": duplicates_skipped,
    }


if __name__ == "__main__":
    from scraper.config import load_config

    cfg = load_config()
    conn = psycopg2.connect(cfg["DATABASE_URL"])
    print(migrate_csv("data/uw_alerts_clean.csv", conn))
    conn.close()
