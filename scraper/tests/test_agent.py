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


CONFIG_DIRECT = {
    "USE_AZURE": False,
    "ANTHROPIC_API_KEY": "sk-t",
    "GOOGLE_MAPS_API_KEY": "gm-t",
    "DATABASE_URL": "pg://localhost/t",
}

CONFIG_AZURE = {
    "USE_AZURE": True,
    "AZURE_ANTHROPIC_BASE_URL": "https://my-azure.example.com",
    "AZURE_ANTHROPIC_API_KEY": "azure-key",
    "AZURE_ANTHROPIC_DEPLOYMENT": "claude-sonnet-4-5",
    "GOOGLE_MAPS_API_KEY": "gm-t",
    "DATABASE_URL": "pg://localhost/t",
}

# Keep old name so existing callers don't break
CONFIG = CONFIG_DIRECT


@patch("scraper.scraper_agent.psycopg2.connect")
@patch("scraper.scraper_agent.get_anthropic_client")
def test_exits_0_on_mark_no_update(mock_get_client, mock_pg):
    mock_get_client.return_value.messages.create.return_value = _tool_response(
        "mark_no_update", {"reason": "already in DB"}
    )
    from scraper.scraper_agent import run_agent

    assert run_agent(CONFIG_DIRECT) == 0


@patch("scraper.scraper_agent.psycopg2.connect")
@patch("scraper.scraper_agent.get_anthropic_client")
def test_dry_run_skips_write(mock_get_client, mock_pg, monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    mock_get_client.return_value.messages.create.return_value = _tool_response(
        "upsert_alert",
        {
            "is_new_incident": True,
            "alert_type": "original",
            "full_text": "test",
            "raw_scraped_text": "test",
        },
    )
    from scraper.scraper_agent import run_agent

    assert run_agent(CONFIG_DIRECT) == 0


@patch("scraper.scraper_agent.psycopg2.connect")
@patch("scraper.scraper_agent.get_anthropic_client")
def test_tools_list_contains_all_five_tools(mock_get_client, mock_pg):
    mock_get_client.return_value.messages.create.return_value = _tool_response(
        "mark_no_update", {"reason": "test"}
    )
    from scraper.scraper_agent import run_agent, TOOLS

    tool_names = {t["name"] for t in TOOLS}
    assert tool_names == {
        "scrape_uw_blog",
        "query_recent_incidents",
        "geocode_address",
        "upsert_alert",
        "mark_no_update",
    }
    run_agent(CONFIG_DIRECT)


@patch("scraper.scraper_agent.psycopg2.connect")
@patch("scraper.scraper_agent.get_anthropic_client")
def test_azure_config_reaches_agent(mock_get_client, mock_pg):
    mock_get_client.return_value.messages.create.return_value = _tool_response(
        "mark_no_update", {"reason": "already in DB"}
    )
    from scraper.scraper_agent import run_agent

    assert run_agent(CONFIG_AZURE) == 0
    mock_get_client.assert_called_once_with(CONFIG_AZURE)


@patch("scraper.scraper_agent.psycopg2.connect")
@patch("scraper.scraper_agent.get_anthropic_client")
def test_azure_model_name_used(mock_get_client, mock_pg):
    mock_get_client.return_value.messages.create.return_value = _tool_response(
        "mark_no_update", {"reason": "done"}
    )
    from scraper.scraper_agent import run_agent

    run_agent(CONFIG_AZURE)
    call_kwargs = mock_get_client.return_value.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-4-5"
