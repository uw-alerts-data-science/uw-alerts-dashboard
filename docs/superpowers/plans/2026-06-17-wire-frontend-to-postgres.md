# Wire Flask Frontend to Postgres Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Flask app's CSV data source with the PostgreSQL database populated by the scraper agent, with zero changes to the existing visualization layer.

**Architecture:** A new thin adapter module `db.py` queries Postgres and returns a `pd.DataFrame` in exactly the shape the existing `visualization_manager` already expects — columns `Incident ID`, `Alert ID`, `Incident Category`, `Incident Alert`, `Nearest Address to Incident`, `Date`, `Report Time`, `geometry`. The three read routes in `uw-alert-web.py` swap their `pd.read_csv` + `get_urgent_incidents` calls for a single `db.query_incidents_as_dataframe(hours)` call. The `fully_update` route is rewired to invoke the scraper agent subprocess instead of the old CSV scraper.

**Tech Stack:** psycopg2 (already installed), pandas, Flask, Python `subprocess`, unittest with `unittest.mock`

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `uw-alert-web/db.py` | **Create** | Postgres connection + `query_incidents_as_dataframe(hours)` |
| `uw-alert-web/tests/test_db.py` | **Create** | Unit tests for `db.py` (mocked psycopg2) |
| `uw-alert-web/uw-alert-web.py` | **Modify** | Replace CSV reads; rewire `fully_update` |

The visualization manager (`visualization_manager.py`) and its tests are **not touched**.

---

## Column Mapping: Postgres → DataFrame

The viz manager expects these columns exactly. The query produces them:

| DataFrame column | Source |
|-----------------|--------|
| `Incident ID` | `incidents.id` |
| `Alert ID` | `alerts.id` |
| `Incident Category` | `incidents.category` |
| `Incident Alert` | `COALESCE(alerts.summary, alerts.full_text)` |
| `Nearest Address to Incident` | `incidents.nearest_address` |
| `Date` | `incidents.first_reported_at` → `strftime("%Y-%m-%d")` |
| `Report Time` | `incidents.first_reported_at` → `strftime("%H:%M:%S")` |
| `geometry` | `{"location": {"lat": incidents.lat, "lng": incidents.lng}}` |

Only rows where `lat IS NOT NULL` are returned (unmappable incidents are excluded).

---

## Task 1: Write `db.py`

**Files:**
- Create: `uw-alert-web/db.py`

- [ ] **Step 1: Create `uw-alert-web/db.py`**

```python
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
        If given, only return incidents whose first_reported_at is within
        the last `hours` hours. None returns all incidents.

    Returns
    -------
    pd.DataFrame with columns:
        Incident ID, Alert ID, Incident Category, Incident Alert,
        Nearest Address to Incident, Date, Report Time, geometry
    """
    where_clause = ""
    params: tuple = ()
    if hours is not None:
        where_clause = "WHERE i.lat IS NOT NULL AND i.first_reported_at >= NOW() - INTERVAL '%s hours'"
        params = (hours,)
    else:
        where_clause = "WHERE i.lat IS NOT NULL"

    sql = f"""
        SELECT
            i.id                                        AS incident_id,
            a.id                                        AS alert_id,
            i.category,
            COALESCE(a.summary, a.full_text)            AS alert_text,
            i.nearest_address,
            i.first_reported_at,
            i.lat,
            i.lng
        FROM incidents i
        JOIN alerts a ON a.incident_id = i.id
        {where_clause}
        ORDER BY i.first_reported_at DESC
    """

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    finally:
        conn.close()

    if not rows:
        return pd.DataFrame(columns=[
            "Incident ID", "Alert ID", "Incident Category", "Incident Alert",
            "Nearest Address to Incident", "Date", "Report Time", "geometry",
        ])

    records = []
    for incident_id, alert_id, category, alert_text, nearest_address, reported_at, lat, lng in rows:
        records.append({
            "Incident ID": incident_id,
            "Alert ID": alert_id,
            "Incident Category": category,
            "Incident Alert": alert_text,
            "Nearest Address to Incident": nearest_address,
            "Date": reported_at.strftime("%Y-%m-%d") if reported_at else None,
            "Report Time": reported_at.strftime("%H:%M:%S") if reported_at else None,
            "geometry": {"location": {"lat": float(lat), "lng": float(lng)}},
        })

    return pd.DataFrame(records)
```

- [ ] **Step 2: Verify it parses without errors**

```bash
cd uw-alert-web && uv run python -c "import db; print('ok')"
```
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add uw-alert-web/db.py
git commit -m "feat(web): add db.py — Postgres → DataFrame adapter for viz manager"
```

---

## Task 2: Write tests for `db.py`

**Files:**
- Create: `uw-alert-web/tests/test_db.py`

- [ ] **Step 1: Write failing tests**

```python
"""Tests for db.py — all psycopg2 calls are mocked."""

import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
import os

import pandas as pd


class TestQueryIncidentsAsDataframe(unittest.TestCase):

    def _make_conn(self, rows):
        """Return a mock psycopg2 connection whose cursor fetchall returns rows."""
        cur = MagicMock()
        cur.fetchall.return_value = rows
        cur.__enter__ = lambda s: s
        cur.__exit__ = MagicMock(return_value=False)
        conn = MagicMock()
        conn.cursor.return_value = cur
        return conn, cur

    @patch("db.get_connection")
    def test_returns_dataframe_with_correct_columns(self, mock_get_conn):
        from db import query_incidents_as_dataframe
        ts = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
        conn, _ = self._make_conn([
            (1, 10, "Robbery", "Pepper spray robbery", "12th Ave NE", ts, 47.656, -122.315),
        ])
        mock_get_conn.return_value = conn

        df = query_incidents_as_dataframe()

        expected_cols = {
            "Incident ID", "Alert ID", "Incident Category", "Incident Alert",
            "Nearest Address to Incident", "Date", "Report Time", "geometry",
        }
        self.assertEqual(set(df.columns), expected_cols)

    @patch("db.get_connection")
    def test_maps_row_values_correctly(self, mock_get_conn):
        from db import query_incidents_as_dataframe
        ts = datetime(2024, 3, 15, 10, 30, 0, tzinfo=timezone.utc)
        conn, _ = self._make_conn([
            (1, 10, "Robbery", "A robbery occurred", "12th Ave NE", ts, 47.656, -122.315),
        ])
        mock_get_conn.return_value = conn

        df = query_incidents_as_dataframe()
        row = df.iloc[0]

        self.assertEqual(row["Incident ID"], 1)
        self.assertEqual(row["Alert ID"], 10)
        self.assertEqual(row["Incident Category"], "Robbery")
        self.assertEqual(row["Incident Alert"], "A robbery occurred")
        self.assertEqual(row["Nearest Address to Incident"], "12th Ave NE")
        self.assertEqual(row["Date"], "2024-03-15")
        self.assertEqual(row["Report Time"], "10:30:00")
        self.assertEqual(row["geometry"], {"location": {"lat": 47.656, "lng": -122.315}})

    @patch("db.get_connection")
    def test_empty_result_returns_empty_dataframe_with_columns(self, mock_get_conn):
        from db import query_incidents_as_dataframe
        conn, _ = self._make_conn([])
        mock_get_conn.return_value = conn

        df = query_incidents_as_dataframe()

        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 0)
        self.assertIn("Incident ID", df.columns)

    @patch("db.get_connection")
    def test_hours_filter_passes_param(self, mock_get_conn):
        from db import query_incidents_as_dataframe
        conn, cur = self._make_conn([])
        mock_get_conn.return_value = conn

        query_incidents_as_dataframe(hours=168)

        call_args = cur.execute.call_args
        sql, params = call_args[0]
        self.assertIn("INTERVAL", sql)
        self.assertEqual(params, (168,))

    @patch("db.get_connection")
    def test_null_reported_at_produces_none_date(self, mock_get_conn):
        from db import query_incidents_as_dataframe
        conn, _ = self._make_conn([
            (2, 20, "Theft", "Theft occurred", "Red Square", None, 47.655, -122.310),
        ])
        mock_get_conn.return_value = conn

        df = query_incidents_as_dataframe()
        row = df.iloc[0]

        self.assertIsNone(row["Date"])
        self.assertIsNone(row["Report Time"])

    def test_get_connection_raises_without_env(self):
        from db import get_connection
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("DATABASE_URL", None)
            with self.assertRaises(RuntimeError):
                get_connection()


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests — expect failures (module not yet importable from test dir)**

```bash
cd uw-alert-web && uv run python -m unittest tests.test_db -v
```
Expected: 6 tests run, all PASS (db.py already exists from Task 1)

- [ ] **Step 3: Commit**

```bash
git add uw-alert-web/tests/test_db.py
git commit -m "test(web): add unit tests for db.py"
```

---

## Task 3: Replace CSV loading in Flask routes

**Files:**
- Modify: `uw-alert-web/uw-alert-web.py`

The three read routes (`/`, `/demo` GET, `/past`) all do the same CSV + `get_urgent_incidents` pattern. Replace them with `db.query_incidents_as_dataframe(hours)` which already pre-filters by time.

Note: `get_urgent_incidents` does two things — time filter + grouping alerts per incident. Since `query_incidents_as_dataframe(hours)` pre-filters by time, we still pass the result through `get_urgent_incidents` with a large `time_frame` to get the grouping step (`combine_text`). The simplest approach: pass `time_frame=10_000_000` (effectively "all") after pre-filtering in SQL.

- [ ] **Step 1: Update imports at the top of `uw-alert-web/uw-alert-web.py`**

Remove `import ast` (no longer needed for CSV parsing). Add the db import. The top of the file becomes:

```python
import os
import io
import json
import pandas as pd
import openai
import googlemaps
from flask import Flask, render_template, request, redirect, url_for
from dotenv import load_dotenv

from .visualization_manager.visualization_manager import get_folium_map
from .visualization_manager.visualization_manager import (
    get_urgent_incidents,
    attach_marker_ids,
)
from .parse_uw_alerts import parse_uw_alerts
from . import db
```

- [ ] **Step 2: Replace `render_home_page`**

```python
@app.route("/")
def render_home_page():
    alert_df = db.query_incidents_as_dataframe(hours=24 * 7)
    urgent_alerts_df = get_urgent_incidents(alert_df, time_frame=10_000_000)
    alert_map, marker_dict = get_folium_map(urgent_alerts_df)
    updated_map, updated_marker_dict = attach_marker_ids(alert_map, marker_dict)
    marker_json = json.dumps(updated_marker_dict)
    return render_template("home.html", map_html=updated_map, alert_dict=marker_json)
```

- [ ] **Step 3: Replace `render_demo_page`**

```python
@app.route("/demo", methods=["GET"])
def render_demo_page():
    alert_df = db.query_incidents_as_dataframe(hours=24)
    urgent_alerts_df = get_urgent_incidents(alert_df, time_frame=10_000_000)
    alert_map, marker_dict = get_folium_map(urgent_alerts_df)
    updated_map, updated_marker_dict = attach_marker_ids(alert_map, marker_dict)
    marker_json = json.dumps(updated_marker_dict)
    return render_template("demo.html", map_html=updated_map, alert_dict=marker_json)
```

- [ ] **Step 4: Replace `render_past_page`**

```python
@app.route("/past", methods=["GET"])
def render_past_page():
    alert_df = db.query_incidents_as_dataframe()
    urgent_alerts_df = get_urgent_incidents(alert_df, time_frame=10_000_000)
    alert_map, marker_dict = get_folium_map(urgent_alerts_df)
    updated_map, updated_marker_dict = attach_marker_ids(alert_map, marker_dict)
    marker_json = json.dumps(updated_marker_dict)
    return render_template("past.html", map_html=updated_map, alert_dict=marker_json)
```

- [ ] **Step 5: Run the existing test suite — all 17 tests must pass**

```bash
uv run poe test
```
Expected: 17 tests pass (same as before — no viz manager tests changed)

- [ ] **Step 6: Commit**

```bash
git add uw-alert-web/uw-alert-web.py
git commit -m "feat(web): replace CSV reads with Postgres in home/demo/past routes"
```

---

## Task 4: Rewire `fully_update` to the scraper agent

**Files:**
- Modify: `uw-alert-web/uw-alert-web.py`

The old route called `parse_uw_alerts.scrape_uw_alerts()` which is the CSV-based scraper. Replace with a subprocess call to `python -m scraper.scraper_agent`.

- [ ] **Step 1: Add `subprocess` import at the top of `uw-alert-web.py`**

```python
import subprocess
```

- [ ] **Step 2: Replace `fully_update`**

```python
@app.route("/fully_update", methods=["GET"])
def fully_update():
    result = subprocess.run(
        ["python", "-m", "scraper.scraper_agent"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        return f"Scraper failed: {result.stderr}", 500

    alert_df = db.query_incidents_as_dataframe(hours=24 * 7)
    urgent_alerts_df = get_urgent_incidents(alert_df, time_frame=10_000_000)
    alert_map, marker_dict = get_folium_map(urgent_alerts_df)
    updated_map, updated_marker_dict = attach_marker_ids(alert_map, marker_dict)
    marker_json = json.dumps(updated_marker_dict)
    return render_template("home.html", map_html=updated_map, alert_dict=marker_json)
```

- [ ] **Step 3: Run the test suite — all 17 tests must pass**

```bash
uv run poe test
```
Expected: 17 pass

- [ ] **Step 4: Commit**

```bash
git add uw-alert-web/uw-alert-web.py
git commit -m "feat(web): wire /fully_update to scraper agent subprocess"
```

---

## Out of Scope

- `/update_map` (demo text-input POST) — uses the old CSV-based OpenAI parser. Left as-is; the demo page's GET still works via DB. This route is a future cleanup.
- `parse_uw_alerts/` module — not deleted yet since `update_map` still references it.
- Unmappable incidents (no lat/lng) — excluded from all map views by `WHERE i.lat IS NOT NULL`; a future sidebar list could show them.
