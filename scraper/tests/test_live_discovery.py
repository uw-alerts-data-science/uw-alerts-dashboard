# scraper/tests/test_live_discovery.py
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


def _end_turn_response():
    resp = MagicMock()
    resp.stop_reason = "end_turn"
    resp.content = []
    return resp


def _mock_db_conn(fetchone=None):
    conn = MagicMock()
    cur = MagicMock()
    conn.cursor.return_value.__enter__ = MagicMock(return_value=cur)
    conn.cursor.return_value.__exit__ = MagicMock(return_value=False)
    cur.fetchone.return_value = fetchone
    return conn, cur


CONFIG_DIRECT = {
    "USE_AZURE": False,
    "ANTHROPIC_API_KEY": "sk-t",
    "GOOGLE_MAPS_API_KEY": "gm-t",
    "DATABASE_URL": "pg://localhost/t",
}


# ── _discover_urls_to_process ────────────────────────────────────────────────


@patch("scraper.live_discovery.known_source_urls")
@patch("scraper.live_discovery.scrape_article_urls")
def test_page_walk_stops_expanding_when_known_url_found(mock_urls, mock_known):
    mock_urls.side_effect = [
        ["https://emergency.uw.edu/new-a/", "https://emergency.uw.edu/new-b/"],
        ["https://emergency.uw.edu/old-c/"],
    ]
    mock_known.side_effect = [set(), {"https://emergency.uw.edu/old-c/"}]
    from scraper.live_discovery import _discover_urls_to_process

    result = _discover_urls_to_process(MagicMock(), max_pages=4)
    assert mock_urls.call_count == 2
    assert set(result) == {
        "https://emergency.uw.edu/new-a/",
        "https://emergency.uw.edu/new-b/",
        "https://emergency.uw.edu/old-c/",
    }


@patch("scraper.live_discovery.known_source_urls", return_value=set())
@patch("scraper.live_discovery.scrape_article_urls")
def test_page_walk_caps_at_max_pages_and_logs_warning(mock_urls, mock_known):
    mock_urls.side_effect = lambda page_num: [f"https://emergency.uw.edu/p{page_num}/"]
    from scraper.live_discovery import _discover_urls_to_process

    with patch("scraper.live_discovery.logger") as mock_logger:
        result = _discover_urls_to_process(MagicMock(), max_pages=3)
        mock_logger.warning.assert_called_once()
    assert mock_urls.call_count == 3
    assert len(result) == 3


@patch("scraper.live_discovery.known_source_urls", return_value=set())
@patch("scraper.live_discovery.scrape_article_urls")
def test_page_walk_stops_when_page_is_empty(mock_urls, mock_known):
    mock_urls.side_effect = [["https://emergency.uw.edu/only/"], []]
    from scraper.live_discovery import _discover_urls_to_process

    with patch("scraper.live_discovery.logger") as mock_logger:
        result = _discover_urls_to_process(MagicMock(), max_pages=4)
        mock_logger.warning.assert_not_called()
    assert result == ["https://emergency.uw.edu/only/"]


# ── _process_live_article ────────────────────────────────────────────────────


@patch("scraper.live_discovery.record_scrape_hash")
@patch("scraper.live_discovery.get_last_scraped_hash", return_value=None)
@patch("scraper.live_discovery.find_incident_id_by_source_url", return_value=42)
@patch("scraper.live_discovery.scrape_article")
@patch("scraper.live_discovery.get_anthropic_client")
def test_process_live_article_injects_known_incident_id_and_is_no_change(
    mock_get_client, mock_scrape, mock_find, mock_last_hash, mock_record_hash
):
    mock_scrape.return_value = {
        "raw_text": "UPDATE: still investigating",
        "article_url": "https://emergency.uw.edu/known/",
        "scraped_at": "2026-01-01T00:00:00+00:00",
    }
    mock_get_client.return_value.messages.create.return_value = _end_turn_response()
    from scraper.live_discovery import _process_live_article

    result = _process_live_article(
        "https://emergency.uw.edu/known/", CONFIG_DIRECT, MagicMock()
    )
    assert result["status"] == "no_change"
    first_messages = mock_get_client.return_value.messages.create.call_args.kwargs[
        "messages"
    ]
    assert "incident_id=42" in first_messages[0]["content"]
    mock_record_hash.assert_called_once()


@patch("scraper.live_discovery.find_incident_id_by_source_url", return_value=42)
@patch("scraper.live_discovery.get_last_scraped_hash")
@patch("scraper.live_discovery.scrape_article")
@patch("scraper.live_discovery.get_anthropic_client")
def test_process_live_article_skips_llm_when_hash_unchanged(
    mock_get_client, mock_scrape, mock_last_hash, mock_find
):
    import hashlib

    raw_text = "UPDATE: still investigating"
    mock_scrape.return_value = {
        "raw_text": raw_text,
        "article_url": "https://emergency.uw.edu/known/",
        "scraped_at": "2026-01-01T00:00:00+00:00",
    }
    mock_last_hash.return_value = hashlib.sha256(raw_text.encode()).hexdigest()
    from scraper.live_discovery import _process_live_article

    result = _process_live_article(
        "https://emergency.uw.edu/known/", CONFIG_DIRECT, MagicMock()
    )
    assert result == {
        "status": "no_change",
        "alerts_inserted": 0,
        "alerts_duplicate": 0,
    }
    mock_get_client.assert_not_called()


@patch("scraper.live_discovery.record_scrape_hash")
@patch("scraper.live_discovery.get_last_scraped_hash")
@patch("scraper.live_discovery.find_incident_id_by_source_url", return_value=42)
@patch("scraper.live_discovery.scrape_article")
@patch("scraper.live_discovery.get_anthropic_client")
def test_process_live_article_calls_llm_when_hash_changed(
    mock_get_client, mock_scrape, mock_find, mock_last_hash, mock_record_hash
):
    mock_scrape.return_value = {
        "raw_text": "UPDATE at 5pm: new development.\nUPDATE: still investigating",
        "article_url": "https://emergency.uw.edu/known/",
        "scraped_at": "2026-01-01T00:00:00+00:00",
    }
    mock_last_hash.return_value = "a" * 64  # stale hash, doesn't match fresh text
    mock_get_client.return_value.messages.create.return_value = _end_turn_response()
    from scraper.live_discovery import _process_live_article

    _process_live_article("https://emergency.uw.edu/known/", CONFIG_DIRECT, MagicMock())
    mock_get_client.assert_called_once()


@patch("scraper.live_discovery.record_scrape_hash")
@patch("scraper.live_discovery.upsert_alert")
@patch("scraper.live_discovery.find_incident_id_by_source_url", return_value=None)
@patch("scraper.live_discovery.scrape_article")
@patch("scraper.live_discovery.get_anthropic_client")
def test_process_live_article_new_incident_flow(
    mock_get_client, mock_scrape, mock_find, mock_upsert, mock_record_hash
):
    mock_scrape.return_value = {
        "raw_text": "ORIGINAL POST: Robbery near Red Square.",
        "article_url": "https://emergency.uw.edu/new/",
        "scraped_at": "2026-01-01T00:00:00+00:00",
    }
    mock_upsert.return_value = {"status": "inserted", "incident_id": 10, "alert_id": 1}
    mock_get_client.return_value.messages.create.side_effect = [
        _tool_response(
            "upsert_alert",
            {
                "is_new_incident": True,
                "alert_type": "original",
                "full_text": "ORIGINAL POST: Robbery near Red Square.",
                "raw_scraped_text": "ORIGINAL POST: Robbery near Red Square.",
            },
        ),
        _end_turn_response(),
    ]
    from scraper.live_discovery import _process_live_article

    result = _process_live_article(
        "https://emergency.uw.edu/new/", CONFIG_DIRECT, MagicMock()
    )
    assert result["status"] == "inserted"
    assert result["alerts_inserted"] == 1
    first_messages = mock_get_client.return_value.messages.create.call_args_list[
        0
    ].kwargs["messages"]
    assert "never been ingested" in first_messages[0]["content"]


@patch("scraper.live_discovery.record_scrape_hash")
@patch("scraper.live_discovery.get_last_scraped_hash", return_value=None)
@patch("scraper.live_discovery.upsert_alert")
@patch("scraper.live_discovery.find_incident_id_by_source_url", return_value=7)
@patch("scraper.live_discovery.scrape_article")
@patch("scraper.live_discovery.get_anthropic_client")
def test_process_live_article_update_links_to_existing_incident_id(
    mock_get_client,
    mock_scrape,
    mock_find,
    mock_upsert,
    mock_last_hash,
    mock_record_hash,
):
    mock_scrape.return_value = {
        "raw_text": "UPDATE: scene is secure.",
        "article_url": "https://emergency.uw.edu/existing/",
        "scraped_at": "2026-01-01T00:00:00+00:00",
    }
    mock_upsert.return_value = {"status": "inserted", "incident_id": 7, "alert_id": 5}
    mock_get_client.return_value.messages.create.side_effect = [
        _tool_response(
            "upsert_alert",
            {
                "is_new_incident": False,
                "incident_id": 7,
                "alert_type": "update",
                "full_text": "UPDATE: scene is secure.",
                "raw_scraped_text": "UPDATE: scene is secure.",
            },
        ),
        _end_turn_response(),
    ]
    from scraper.live_discovery import _process_live_article

    result = _process_live_article(
        "https://emergency.uw.edu/existing/", CONFIG_DIRECT, MagicMock()
    )
    assert result["status"] == "inserted"
    mock_upsert.assert_called_once()
    assert mock_upsert.call_args.args[1]["incident_id"] == 7
    first_messages = mock_get_client.return_value.messages.create.call_args_list[
        0
    ].kwargs["messages"]
    assert "incident_id=7" in first_messages[0]["content"]


@patch("scraper.live_discovery.find_incident_id_by_source_url", return_value=None)
@patch("scraper.live_discovery.scrape_article")
@patch("scraper.live_discovery.get_anthropic_client")
def test_process_live_article_malformed_upsert_returns_error(
    mock_get_client, mock_scrape, mock_find
):
    conn, cur = _mock_db_conn(fetchone=(1,))
    mock_scrape.return_value = {
        "raw_text": "ORIGINAL POST: something happened",
        "article_url": "https://emergency.uw.edu/bad/",
        "scraped_at": "2026-01-01T00:00:00+00:00",
    }
    mock_get_client.return_value.messages.create.return_value = _tool_response(
        "upsert_alert",
        {
            "is_new_incident": True,
            "alert_type": "original",
            "raw_scraped_text": "missing the required full_text field",
        },
    )
    from scraper.live_discovery import _process_live_article

    result = _process_live_article("https://emergency.uw.edu/bad/", CONFIG_DIRECT, conn)
    assert result["status"] == "error"
    # Validation fails before any write (INSERT/UPDATE) ever happens.
    calls_str = str(cur.execute.call_args_list)
    assert "INSERT" not in calls_str
    assert "UPDATE" not in calls_str


@patch(
    "scraper.live_discovery.upsert_alert",
    side_effect=Exception("insert or update on table violates foreign key constraint"),
)
@patch("scraper.live_discovery.find_incident_id_by_source_url", return_value=None)
@patch("scraper.live_discovery.scrape_article")
@patch("scraper.live_discovery.get_anthropic_client")
def test_process_live_article_rolls_back_connection_on_upsert_error(
    mock_get_client, mock_scrape, mock_find, mock_upsert
):
    """A DB error from upsert_alert must not leave the shared connection poisoned.

    run_live_discovery reuses one connection serially across every article in
    a cycle; an unrolled-back transaction fails every subsequent query on
    that connection with "current transaction is aborted" for the rest of
    the cycle.
    """
    mock_scrape.return_value = {
        "raw_text": "ORIGINAL POST: Robbery near Red Square.",
        "article_url": "https://emergency.uw.edu/new/",
        "scraped_at": "2026-01-01T00:00:00+00:00",
    }
    mock_get_client.return_value.messages.create.side_effect = [
        _tool_response(
            "upsert_alert",
            {
                "is_new_incident": True,
                "alert_type": "original",
                "full_text": "ORIGINAL POST: Robbery near Red Square.",
                "raw_scraped_text": "ORIGINAL POST: Robbery near Red Square.",
            },
        ),
        _end_turn_response(),
    ]
    from scraper.live_discovery import _process_live_article

    conn = MagicMock()
    result = _process_live_article("https://emergency.uw.edu/new/", CONFIG_DIRECT, conn)
    assert result["status"] == "error"
    conn.rollback.assert_called_once()


@patch("scraper.live_discovery.find_incident_id_by_source_url", return_value=None)
@patch("scraper.live_discovery.scrape_article")
def test_process_live_article_scrape_failure_returns_error(mock_scrape, mock_find):
    from scraper.tools.scrape import ScrapingError

    mock_scrape.side_effect = ScrapingError("network error")
    from scraper.live_discovery import _process_live_article

    result = _process_live_article(
        "https://emergency.uw.edu/down/", CONFIG_DIRECT, MagicMock()
    )
    assert result["status"] == "error"
    mock_find.assert_not_called()


# ── LIVE_TOOLS ────────────────────────────────────────────────────────────────


def test_live_tools_excludes_removed_tools():
    from scraper.live_discovery import LIVE_TOOLS

    tool_names = {t["name"] for t in LIVE_TOOLS}
    assert tool_names == {"geocode_address", "upsert_alert"}


# ── run_live_discovery ────────────────────────────────────────────────────────


@patch("scraper.live_discovery.psycopg2.connect")
@patch("scraper.live_discovery._process_live_article")
@patch("scraper.live_discovery._discover_urls_to_process")
def test_run_live_discovery_returns_0_on_success(mock_discover, mock_process, mock_pg):
    mock_discover.return_value = ["url1", "url2"]
    mock_process.side_effect = [
        {"status": "inserted", "alerts_inserted": 1, "alerts_duplicate": 0},
        {"status": "no_change", "alerts_inserted": 0, "alerts_duplicate": 0},
    ]
    from scraper.live_discovery import run_live_discovery

    assert run_live_discovery(CONFIG_DIRECT) == 0


@patch("scraper.live_discovery.psycopg2.connect")
@patch("scraper.live_discovery._discover_urls_to_process", return_value=[])
def test_run_live_discovery_returns_0_when_nothing_to_process(mock_discover, mock_pg):
    from scraper.live_discovery import run_live_discovery

    assert run_live_discovery(CONFIG_DIRECT) == 0


@patch("scraper.live_discovery.psycopg2.connect")
@patch("scraper.live_discovery._process_live_article")
@patch("scraper.live_discovery._discover_urls_to_process")
def test_run_live_discovery_returns_1_when_all_errors_no_inserts(
    mock_discover, mock_process, mock_pg
):
    mock_discover.return_value = ["url1"]
    mock_process.return_value = {
        "status": "error",
        "error": "boom",
        "alerts_inserted": 0,
        "alerts_duplicate": 0,
    }
    from scraper.live_discovery import run_live_discovery

    assert run_live_discovery(CONFIG_DIRECT) == 1
