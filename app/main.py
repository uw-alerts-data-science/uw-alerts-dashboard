"""
Fast API backend for uw alerts
"""

import os
from typing import Iterator

from fastapi import Depends, FastAPI
import psycopg2
from psycopg2.extensions import connection as PgConnection

from scraper.tools.database import query_recent_incidents, search_incidents


app = FastAPI()


def get_db_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return url


def get_db() -> Iterator[PgConnection]:
    """Yield a Postgress connection, guaranteed closed after the response"""
    conn = psycopg2.connect(get_db_url())
    try:
        yield conn
    finally:
        conn.close()


@app.get("/health")
def health(conn: PgConnection = Depends(get_db)):
    """Health check to establish connection to database"""
    return {"status": "healthy"}


@app.get("/query/incidents/recent")
def get_recent_incidents(conn: PgConnection = Depends(get_db), limit: int = 10):
    """This is just a test to see if we can connect"""
    return query_recent_incidents(conn, limit)


@app.get("/query/incidents/search")
def search(keywords: str, conn: PgConnection = Depends(get_db)):
    return search_incidents(conn, keywords)
