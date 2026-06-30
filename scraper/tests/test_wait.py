import psycopg2
import pytest
from unittest.mock import MagicMock, patch


def test_wait_succeeds_immediately():
    with patch("scraper.db.wait.psycopg2.connect") as mock_connect:
        mock_connect.return_value = MagicMock()
        from scraper.db.wait import wait_for_postgres
        wait_for_postgres(url="postgres://localhost/test", interval=0)
        mock_connect.assert_called_once_with("postgres://localhost/test")


def test_wait_retries_then_succeeds():
    with patch("scraper.db.wait.psycopg2.connect") as mock_connect:
        mock_connect.side_effect = [
            psycopg2.OperationalError(),
            psycopg2.OperationalError(),
            MagicMock(),
        ]
        from scraper.db.wait import wait_for_postgres
        wait_for_postgres(url="postgres://localhost/test", interval=0)
        assert mock_connect.call_count == 3


def test_wait_raises_timeout():
    with patch("scraper.db.wait.psycopg2.connect") as mock_connect:
        mock_connect.side_effect = psycopg2.OperationalError()
        from scraper.db.wait import wait_for_postgres
        with pytest.raises(TimeoutError, match="not ready after"):
            wait_for_postgres(url="postgres://localhost/test", timeout=0.05, interval=0)
