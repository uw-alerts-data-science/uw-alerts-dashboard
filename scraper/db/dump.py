import os
import pandas as pd


def dump_to_csv(conn, output_dir: str = "data/snapshot") -> dict:
    """Export incidents and alerts tables to CSV files for seeding."""
    os.makedirs(output_dir, exist_ok=True)

    incidents_path = os.path.join(output_dir, "incidents.csv")
    alerts_path = os.path.join(output_dir, "alerts.csv")

    incidents_df = pd.read_sql("SELECT * FROM incidents ORDER BY id", conn)
    incidents_df.to_csv(incidents_path, index=False)

    alerts_df = pd.read_sql("SELECT * FROM alerts ORDER BY id", conn)
    alerts_df.to_csv(alerts_path, index=False)

    return {
        "incidents_exported": len(incidents_df),
        "alerts_exported": len(alerts_df),
        "incidents_path": incidents_path,
        "alerts_path": alerts_path,
    }


if __name__ == "__main__":
    import psycopg2
    from scraper.config import load_config

    cfg = load_config()
    conn = psycopg2.connect(cfg["DATABASE_URL"])
    result = dump_to_csv(conn)
    print(result)
    conn.close()
