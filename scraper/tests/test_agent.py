# scraper/tests/test_agent.py
from unittest.mock import patch


@patch("scraper.agent.run_live_discovery")
def test_run_agent_forwards_to_run_live_discovery(mock_run):
    mock_run.return_value = 0
    from scraper.agent import run_agent

    config = {"DATABASE_URL": "pg://localhost/t"}
    assert run_agent(config) == 0
    mock_run.assert_called_once_with(config)
