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


@patch("scraper.agent.psycopg2.connect")
@patch("scraper.agent.get_anthropic_client")
def test_exits_0_on_mark_no_update(mock_get_client, mock_pg):
    mock_get_client.return_value.messages.create.return_value = _tool_response(
        "mark_no_update", {"reason": "already in DB"}
    )
    from scraper.agent import run_agent

    assert run_agent(CONFIG_DIRECT) == 0


@patch("scraper.agent.psycopg2.connect")
@patch("scraper.agent.get_anthropic_client")
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
    from scraper.agent import run_agent

    assert run_agent(CONFIG_DIRECT) == 0


@patch("scraper.agent.psycopg2.connect")
@patch("scraper.agent.get_anthropic_client")
def test_tools_list_contains_all_five_tools(mock_get_client, mock_pg):
    mock_get_client.return_value.messages.create.return_value = _tool_response(
        "mark_no_update", {"reason": "test"}
    )
    from scraper.agent import run_agent, TOOLS

    tool_names = {t["name"] for t in TOOLS}
    assert tool_names == {
        "scrape_uw_blog",
        "query_recent_incidents",
        "geocode_address",
        "upsert_alert",
        "mark_no_update",
    }
    run_agent(CONFIG_DIRECT)


@patch("scraper.agent.psycopg2.connect")
@patch("scraper.agent.get_anthropic_client")
def test_azure_config_reaches_agent(mock_get_client, mock_pg):
    mock_get_client.return_value.messages.create.return_value = _tool_response(
        "mark_no_update", {"reason": "already in DB"}
    )
    from scraper.agent import run_agent

    assert run_agent(CONFIG_AZURE) == 0
    mock_get_client.assert_called_once_with(CONFIG_AZURE)


@patch("scraper.agent.psycopg2.connect")
@patch("scraper.agent.get_anthropic_client")
def test_azure_model_name_used(mock_get_client, mock_pg):
    mock_get_client.return_value.messages.create.return_value = _tool_response(
        "mark_no_update", {"reason": "done"}
    )
    from scraper.agent import run_agent

    run_agent(CONFIG_AZURE)
    call_kwargs = mock_get_client.return_value.messages.create.call_args.kwargs
    assert call_kwargs["model"] == "claude-sonnet-4-5"


def _mock_db_conn(fetchone=None):
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    cur.fetchone.return_value = fetchone
    return conn, cur


@patch("scraper.agent.psycopg2.connect")
@patch("scraper.agent.get_anthropic_client")
def test_new_incident_creates_incident_and_alert_rows(mock_get_client, mock_pg):
    conn, cur = _mock_db_conn(fetchone=(10,))
    mock_pg.return_value = conn
    mock_get_client.return_value.messages.create.return_value = _tool_response(
        "upsert_alert",
        {
            "is_new_incident": True,
            "alert_type": "original",
            "full_text": "ORIGINAL POST: Robbery near Red Square.",
            "raw_scraped_text": "ORIGINAL POST: Robbery near Red Square.",
            "category": "Robbery",
        },
    )
    from scraper.agent import run_agent

    assert run_agent(CONFIG_DIRECT) == 0
    calls_str = str(cur.execute.call_args_list)
    assert "INSERT INTO incidents" in calls_str
    assert "INSERT INTO alerts" in calls_str
    assert "Robbery" in calls_str


@patch("scraper.agent.psycopg2.connect")
@patch("scraper.agent.get_anthropic_client")
def test_update_links_to_existing_incident_id(mock_get_client, mock_pg):
    conn, cur = _mock_db_conn(fetchone=(500,))
    mock_pg.return_value = conn
    mock_get_client.return_value.messages.create.return_value = _tool_response(
        "upsert_alert",
        {
            "is_new_incident": False,
            "incident_id": 42,
            "alert_type": "update",
            "full_text": "UPDATE: scene is secure.",
            "raw_scraped_text": "UPDATE: scene is secure.",
        },
    )
    from scraper.agent import run_agent

    assert run_agent(CONFIG_DIRECT) == 0
    calls_str = str(cur.execute.call_args_list)
    assert "INSERT INTO incidents" not in calls_str
    assert "UPDATE incidents SET last_updated_at=NOW() WHERE id=%s" in calls_str
    assert "(42,)" in calls_str


@patch("scraper.agent.psycopg2.connect")
@patch("scraper.agent.get_anthropic_client")
def test_malformed_upsert_call_missing_full_text_returns_1(mock_get_client, mock_pg):
    conn, cur = _mock_db_conn(fetchone=(1,))
    mock_pg.return_value = conn
    mock_get_client.return_value.messages.create.return_value = _tool_response(
        "upsert_alert",
        {
            "is_new_incident": True,
            "alert_type": "original",
            "raw_scraped_text": "missing the required full_text field",
        },
    )
    from scraper.agent import run_agent

    assert run_agent(CONFIG_DIRECT) == 1
    cur.execute.assert_not_called()
