import os
from pathlib import Path

import psycopg2


def apply_schema(url=None):
    url = url or os.environ["DATABASE_URL"]
    sql = (Path(__file__).parent / "schema.sql").read_text()
    conn = psycopg2.connect(url)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql)
        print("Schema applied.")
    finally:
        conn.close()
