import ast, hashlib, sys
import pandas as pd
import psycopg2, psycopg2.errors


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
            cur.execute("""
                INSERT INTO incidents (category, nearest_address, google_address,
                    lat, lng, first_reported_at, last_updated_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id
            """, (first.get("Incident Category"), first.get("Nearest Address to Incident"),
                  first.get("Google Address"), lat, lng,
                  pd.to_datetime(str(first["Date"])).isoformat() if first.get("Date") else None,
                  pd.to_datetime(str(group.iloc[-1]["Date"])).isoformat() if first.get("Date") else None))
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
                        reported = pd.to_datetime(f"{row['Date']} {row['Report Time']}").isoformat()
                    except Exception:
                        pass
                cur.execute("""
                    INSERT INTO alerts (incident_id, alert_type, reported_at,
                        summary, full_text, raw_scraped_text, source_url, text_hash)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """, (inc_db_id, str(row.get("Alert Type") or "original").lower(),
                      reported, row.get("Incident Summary"),
                      full_text, full_text, "https://emergency.uw.edu/", text_hash))
            conn.commit()
            alerts_inserted += 1
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            duplicates_skipped += 1

    return {"incidents_inserted": incidents_inserted,
            "alerts_inserted": alerts_inserted,
            "duplicates_skipped": duplicates_skipped}


if __name__ == "__main__":
    from scraper.config import load_config
    cfg = load_config()
    conn = psycopg2.connect(cfg["DATABASE_URL"])
    print(migrate_csv("data/uw_alerts_clean.csv", conn))
    conn.close()
