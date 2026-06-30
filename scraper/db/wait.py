import os
import time

import psycopg2


def wait_for_postgres(url=None, timeout=30, interval=1):
    url = url or os.environ["DATABASE_URL"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            conn = psycopg2.connect(url)
            conn.close()
            print("Postgres is ready.")
            return
        except psycopg2.OperationalError:
            time.sleep(interval)
    raise TimeoutError(f"Postgres not ready after {timeout}s — is Docker running?")
