# scraper/tests/test_agent.py
from unittest.mock import MagicMock, patch


def _tool_response(name, inputs, uid="tu_1"):
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.input = inputs
    block.id = uid
    resp = MagicMock()
    resp.stop_reason = "tool_use"
    resp.content = [block]
    return resp


CONFIG = {"ANTHROPIC_API_KEY": "sk-t", "GOOGLE_MAPS_API_KEY": "gm-t", "DATABASE_URL": "pg://localhost/t"}


@patch("scraper.scraper_agent.psycopg2.connect")
@patch("scraper.scraper_agent.anthropic.Anthropic")
def test_exits_0_on_mark_no_update(mock_cls, mock_pg):
    mock_cls.return_value.messages.create.return_value = _tool_response(
        "mark_no_update", {"reason": "already in DB"})
    from scraper.scraper_agent import run_agent
    assert run_agent(CONFIG) == 0


@patch("scraper.scraper_agent.psycopg2.connect")
@patch("scraper.scraper_agent.anthropic.Anthropic")
def test_dry_run_skips_write(mock_cls, mock_pg, monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    mock_cls.return_value.messages.create.return_value = _tool_response(
        "upsert_alert", {"is_new_incident": True, "alert_type": "original",
                         "full_text": "test", "raw_scraped_text": "test"})
    from scraper.scraper_agent import run_agent
    result = run_agent(CONFIG)
    assert result == 0


@patch("scraper.scraper_agent.psycopg2.connect")
@patch("scraper.scraper_agent.anthropic.Anthropic")
def test_tools_list_contains_all_five_tools(mock_cls, mock_pg):
    mock_cls.return_value.messages.create.return_value = _tool_response(
        "mark_no_update", {"reason": "test"})
    from scraper.scraper_agent import run_agent, TOOLS
    tool_names = {t["name"] for t in TOOLS}
    assert tool_names == {"scrape_uw_blog", "query_recent_incidents",
                          "geocode_address", "upsert_alert", "mark_no_update"}
    run_agent(CONFIG)
