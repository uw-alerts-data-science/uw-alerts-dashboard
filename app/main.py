"""FastAPI backend for UW Alerts."""

import os
from datetime import datetime
from typing import Iterator

import psycopg2
from fastapi import Depends, FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from psycopg2.extensions import connection as PgConnection
from pydantic import BaseModel

from scraper.tools.database import query_recent_incidents, search_incidents


app = FastAPI(
    title="UW Alerts API",
    version="0.2.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://uwalerts.live",
        "https://www.uwalerts.live",
    ],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


class AlertMarker(BaseModel):
    id: int
    title: str
    category: str
    address: str
    latitude: float
    longitude: float
    reportedAt: datetime | None


class AlertsResponse(BaseModel):
    alerts: list[AlertMarker]


def get_db_url() -> str:
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is not set")

    return database_url


def get_db() -> Iterator[PgConnection]:
    """Yield a PostgreSQL connection and close it after the request."""

    conn = psycopg2.connect(get_db_url())

    try:
        yield conn
    finally:
        conn.close()


@app.get("/health")
def health(conn: PgConnection = Depends(get_db)):
    """Verify that the API can connect to PostgreSQL."""

    with conn.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()

    return {"status": "healthy"}


@app.get("/query/incidents/recent")
def get_recent_incidents(
    limit: int = Query(default=10, ge=1, le=500),
    conn: PgConnection = Depends(get_db),
):
    """Return recently reported incidents using the existing database helper."""

    return query_recent_incidents(conn, limit)


@app.get("/query/incidents/search")
def search(
    keywords: str,
    conn: PgConnection = Depends(get_db),
):
    """Search incidents by address, category, or alert text."""

    return search_incidents(conn, keywords)


@app.get("/api/alerts", response_model=AlertsResponse)
def get_map_alerts(
    hours: int | None = Query(default=None, ge=1, le=720),
    limit: int = Query(default=500, ge=1, le=5000),
    conn: PgConnection = Depends(get_db),
):
    """
    Return map-ready incidents.

    When hours is provided, only incidents with an alert inserted by the
    scraper during that time window are returned.
    """

    recent_filter = ""
    parameters: list[int] = []

    if hours is not None:
        recent_filter = """
            AND scraped.scraped_at >=
                NOW() - (%s * INTERVAL '1 hour')
        """
        parameters.append(hours)

    parameters.append(limit)

    order_by = (
        "scraped.scraped_at DESC NULLS LAST"
        if hours is not None
        else "reported_at DESC NULLS LAST"
    )

    query = f"""
        SELECT
            i.id,

            COALESCE(
                NULLIF(latest_alert.summary, ''),
                COALESCE(i.category, 'Other') || ' Alert'
            ) AS title,

            COALESCE(i.category, 'Other') AS category,

            COALESCE(
                i.google_address,
                i.nearest_address,
                'Location unavailable'
            ) AS address,

            i.lat::float AS latitude,
            i.lng::float AS longitude,

            COALESCE(
                latest_alert.reported_at,
                i.first_reported_at,
                i.occurred_at,
                i.created_at
            ) AS reported_at,

            scraped.scraped_at

        FROM incidents i

        LEFT JOIN LATERAL (
            SELECT
                a.summary,
                a.reported_at,
                a.created_at
            FROM alerts a
            WHERE a.incident_id = i.id
            ORDER BY
                a.reported_at DESC NULLS LAST,
                a.created_at DESC
            LIMIT 1
        ) latest_alert ON true

        LEFT JOIN LATERAL (
            SELECT MAX(a.created_at) AS scraped_at
            FROM alerts a
            WHERE a.incident_id = i.id
        ) scraped ON true

        WHERE i.lat IS NOT NULL
          AND i.lng IS NOT NULL
          {recent_filter}

        ORDER BY {order_by}
        LIMIT %s;
    """

    with conn.cursor() as cursor:
        cursor.execute(query, tuple(parameters))
        rows = cursor.fetchall()

    alerts = [
        AlertMarker(
            id=row[0],
            title=row[1],
            category=row[2],
            address=row[3],
            latitude=row[4],
            longitude=row[5],
            reportedAt=row[6],
        )
        for row in rows
    ]

    return AlertsResponse(alerts=alerts)
