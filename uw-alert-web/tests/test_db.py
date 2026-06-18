"""Tests for db.py — all psycopg2 calls are mocked."""

import os
import unittest
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pandas as pd

from db import get_connection, query_incidents_as_dataframe


class TestQueryIncidentsAsDataframe(unittest.TestCase):

    def _make_conn(self, rows):
        """Return a mock psycopg2 connection whose cursor fetchall returns rows."""
        cur = MagicMock()
        cur.fetchall.return_value = rows
        cur.__enter__ = MagicMock(return_value=cur)
        cur.__exit__ = MagicMock(return_value=False)
        conn = MagicMock()
        conn.cursor.return_value = cur
        return conn, cur

    @patch("db.get_connection")
    def test_returns_dataframe_with_correct_columns(self, mock_get_conn):
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
        self.assertEqual(len(df), 1)  # confirm row was processed, not just empty schema

    @patch("db.get_connection")
    def test_maps_row_values_correctly(self, mock_get_conn):
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
        conn, _ = self._make_conn([])
        mock_get_conn.return_value = conn

        df = query_incidents_as_dataframe()

        self.assertIsInstance(df, pd.DataFrame)
        self.assertEqual(len(df), 0)
        self.assertIn("Incident ID", df.columns)

    @patch("db.get_connection")
    def test_hours_filter_passes_param(self, mock_get_conn):
        conn, cur = self._make_conn([])
        mock_get_conn.return_value = conn

        query_incidents_as_dataframe(hours=168)

        call_args = cur.execute.call_args
        sql, params = call_args[0]
        self.assertIn("INTERVAL", sql)
        self.assertEqual(params, (168,))

    @patch("db.get_connection")
    def test_null_reported_at_produces_none_date(self, mock_get_conn):
        conn, _ = self._make_conn([
            (2, 20, "Theft", "Theft occurred", "Red Square", None, 47.655, -122.310),
        ])
        mock_get_conn.return_value = conn

        df = query_incidents_as_dataframe()
        row = df.iloc[0]

        self.assertIsNone(row["Date"])
        self.assertIsNone(row["Report Time"])

    def test_get_connection_raises_without_env(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                get_connection()


if __name__ == "__main__":
    unittest.main()
