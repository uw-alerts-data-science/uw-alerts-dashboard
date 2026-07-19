import os
import psycopg2
import pandas as pd


def get_connection():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return psycopg2.connect(url)


def query_incidents_as_dataframe(hours: int | None = None) -> pd.DataFrame:
    """Query incidents+alerts from Postgres and return a DataFrame shaped for
    the visualization manager.

    Only incidents with a geocoded location (lat IS NOT NULL) are returned.
    Each row is one alert; incidents with multiple alerts produce multiple rows.

    Parameters
    ----------
    hours:
        If given, only return alerts whose reported_at (fallback: incident first_reported_at)
        is within the last `hours` hours. None returns all alerts.
    Returns
    -------
    pd.DataFrame with columns:
        Incident ID, Alert ID, Incident Category, Incident Alert,
        Nearest Address to Incident, Date, Report Time, geometry
    """
    if hours is not None:
        # Match legacy CSV behavior: filter by the alert's published timestamp.
        where_clause = (
            "WHERE i.lat IS NOT NULL "
            "AND COALESCE(a.reported_at, i.first_reported_at) >= NOW() - (INTERVAL '1 hour' * %s)"
        )
        params: tuple = (hours,)
    else:
        where_clause = "WHERE i.lat IS NOT NULL"
        params = ()

    sql = f"""
        SELECT
            i.id                                        AS incident_id,
            a.id                                        AS alert_id,
            i.category,
            COALESCE(a.summary, a.full_text)            AS alert_text,
            i.nearest_address,
            COALESCE(a.reported_at, i.first_reported_at) AS reported_at,
            i.lat,
            i.lng
        FROM incidents i
        JOIN alerts a ON a.incident_id = i.id
        {where_clause}
        ORDER BY COALESCE(a.reported_at, i.first_reported_at) DESC NULLS LAST
    """

    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        if conn:
            conn.close()

    if not rows:
        return pd.DataFrame(
            columns=[
                "Incident ID",
                "Alert ID",
                "Incident Category",
                "Incident Alert",
                "Nearest Address to Incident",
                "Date",
                "Report Time",
                "geometry",
            ]
        )

    records = []
    for (
        incident_id,
        alert_id,
        category,
        alert_text,
        nearest_address,
        reported_at,
        lat,
        lng,
    ) in rows:
        records.append(
            {
                "Incident ID": incident_id,
                "Alert ID": alert_id,
                "Incident Category": category,
                "Incident Alert": alert_text,
                "Nearest Address to Incident": nearest_address,
                "Date": reported_at.strftime("%Y-%m-%d") if reported_at else None,
                "Report Time": reported_at.strftime("%H:%M:%S")
                if reported_at
                else None,
                "geometry": {"location": {"lat": float(lat), "lng": float(lng)}},
            }
        )

    return pd.DataFrame(records)
