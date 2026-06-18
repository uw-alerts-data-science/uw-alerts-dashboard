# scraper/tests/test_batch_history.py
from unittest.mock import MagicMock, patch

CONFIG = {
    "ANTHROPIC_API_KEY": "sk-test",
    "GOOGLE_MAPS_API_KEY": "gm-test",
    "DATABASE_URL": "postgres://localhost/test",
}

SAMPLE_ARTICLE = {
    "raw_text": "UW Alert\nJune 1, 2024\nTheft near HUB. UWPD responding.",
    "article_url": "https://emergency.uw.edu/2024/theft-hub/",
    "scraped_at": "2026-06-17T00:00:00+00:00",
}


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


# ── run_batch_agent ──────────────────────────────────────────────────────────


@patch(
    "scraper.batch_history.upsert_alert",
    return_value={"status": "inserted", "incident_id": 1, "alert_id": 1},
)
@patch("scraper.batch_history.anthropic.Anthropic")
def test_run_batch_agent_upsert_returns_inserted(mock_cls, mock_upsert):
    mock_cls.return_value.messages.create.return_value = _tool_response(
        "upsert_alert",
        {
            "alert_type": "original",
            "full_text": "Theft near HUB.",
            "raw_scraped_text": "Theft near HUB.",
        },
    )
    from scraper.batch_history import run_batch_agent

    conn = MagicMock()
    result = run_batch_agent(SAMPLE_ARTICLE, CONFIG, conn)
    assert result.get("status") == "inserted"
    assert mock_upsert.called


@patch("scraper.batch_history.anthropic.Anthropic")
def test_run_batch_agent_end_turn_returns_error(mock_cls):
    mock_cls.return_value.messages.create.return_value = _end_turn_response()
    from scraper.batch_history import run_batch_agent

    conn = MagicMock()
    result = run_batch_agent(SAMPLE_ARTICLE, CONFIG, conn)
    assert result.get("status") == "error"


@patch("scraper.batch_history.anthropic.Anthropic")
def test_run_batch_agent_returns_error_on_api_failure(mock_cls):
    import anthropic as anthropic_mod

    mock_cls.return_value.messages.create.side_effect = anthropic_mod.APIError(
        message="rate limit", request=MagicMock(), body=None
    )
    from scraper.batch_history import run_batch_agent

    conn = MagicMock()
    result = run_batch_agent(SAMPLE_ARTICLE, CONFIG, conn)
    assert result["status"] == "error"


@patch("scraper.batch_history.anthropic.Anthropic")
def test_run_batch_agent_dry_run_skips_write(mock_cls, monkeypatch):
    monkeypatch.setenv("DRY_RUN", "true")
    mock_cls.return_value.messages.create.return_value = _tool_response(
        "upsert_alert",
        {
            "alert_type": "original",
            "full_text": "test alert",
            "raw_scraped_text": "test alert",
        },
    )
    from scraper.batch_history import run_batch_agent

    conn = MagicMock()
    result = run_batch_agent(SAMPLE_ARTICLE, CONFIG, conn)
    assert result["status"] == "dry_run"
    conn.cursor.assert_not_called()


# ── BATCH_TOOLS schema ───────────────────────────────────────────────────────


def test_batch_tools_contains_expected_names():
    from scraper.batch_history import BATCH_TOOLS

    names = {t["name"] for t in BATCH_TOOLS}
    assert names == {"geocode_address", "upsert_alert"}


def test_batch_tools_upsert_alert_required_fields():
    from scraper.batch_history import BATCH_TOOLS

    upsert = next(t for t in BATCH_TOOLS if t["name"] == "upsert_alert")
    required = set(upsert["input_schema"]["required"])
    assert required == {"alert_type", "full_text", "raw_scraped_text"}


# ── _discover_article_urls ───────────────────────────────────────────────────


@patch(
    "scraper.batch_history.scrape_article_urls",
    return_value=[
        "https://emergency.uw.edu/2024/01/theft/",
        "https://emergency.uw.edu/2024/02/robbery/",
    ],
)
def test_discover_article_urls_returns_flat_list(mock_scrape):
    from scraper.batch_history import _discover_article_urls

    urls = _discover_article_urls(start_page=2, end_page=1, max_pages=50)
    assert len(urls) == 4  # 2 pages × 2 urls


@patch("scraper.batch_history.scrape_article_urls", side_effect=Exception("timeout"))
def test_discover_article_urls_skips_failed_pages(mock_scrape):
    from scraper.batch_history import _discover_article_urls

    urls = _discover_article_urls(start_page=2, end_page=1, max_pages=50)
    assert urls == []


# ── _chunk ───────────────────────────────────────────────────────────────────


def test_chunk_divides_evenly():
    from scraper.batch_history import _chunk

    result = _chunk([1, 2, 3, 4], 2)
    assert len(result) == 2
    assert all(len(c) == 2 for c in result)


def test_chunk_handles_more_workers_than_items():
    from scraper.batch_history import _chunk

    result = _chunk([1, 2], 10)
    assert len(result) == 2
    assert all(len(c) == 1 for c in result)


# ── _process_batch_worker ────────────────────────────────────────────────────


@patch(
    "scraper.batch_history.run_batch_agent",
    return_value={"status": "inserted", "incident_id": 1, "alert_id": 1},
)
@patch("scraper.batch_history.scrape_article", return_value=SAMPLE_ARTICLE)
@patch("scraper.batch_history.psycopg2.connect")
def test_process_batch_worker_calls_agent_for_each_url(
    mock_pg, mock_scrape, mock_agent
):
    from scraper.batch_history import _process_batch_worker

    urls = [
        "https://emergency.uw.edu/2024/01/theft/",
        "https://emergency.uw.edu/2024/02/robbery/",
    ]
    results = _process_batch_worker(urls, CONFIG)
    assert mock_agent.call_count == 2
    assert all(r["status"] == "inserted" for r in results)


@patch("scraper.batch_history.scrape_article", side_effect=Exception("network error"))
@patch("scraper.batch_history.psycopg2.connect")
def test_process_batch_worker_records_scrape_error(mock_pg, mock_scrape):
    from scraper.batch_history import _process_batch_worker

    results = _process_batch_worker(["https://emergency.uw.edu/2024/01/theft/"], CONFIG)
    assert results[0]["status"] == "error"


# ── run_batch ────────────────────────────────────────────────────────────────


@patch(
    "scraper.batch_history._process_batch_worker",
    return_value=[
        {"status": "inserted", "incident_id": 1, "alert_id": 1},
        {"status": "inserted", "incident_id": 2, "alert_id": 2},
    ],
)
@patch(
    "scraper.batch_history._discover_article_urls",
    return_value=[
        "https://emergency.uw.edu/a/",
        "https://emergency.uw.edu/b/",
        "https://emergency.uw.edu/c/",
        "https://emergency.uw.edu/d/",
    ],
)
@patch("scraper.batch_history.psycopg2.connect")
def test_run_batch_counts_inserted(mock_pg, mock_discover, mock_worker):
    mock_pg.return_value.cursor.return_value.__enter__.return_value.fetchall.return_value = []
    from scraper.batch_history import run_batch

    rc = run_batch(CONFIG, max_workers=2)
    assert rc == 0


@patch(
    "scraper.batch_history._process_batch_worker",
    return_value=[
        {"status": "error", "error": "something broke"},
    ],
)
@patch(
    "scraper.batch_history._discover_article_urls",
    return_value=["https://emergency.uw.edu/a/"],
)
@patch("scraper.batch_history.psycopg2.connect")
def test_run_batch_returns_1_when_all_errors_no_inserts(
    mock_pg, mock_discover, mock_worker
):
    mock_pg.return_value.cursor.return_value.__enter__.return_value.fetchall.return_value = []
    from scraper.batch_history import run_batch

    rc = run_batch(CONFIG, max_workers=1)
    assert rc == 1


@patch("scraper.batch_history._discover_article_urls", return_value=[])
@patch("scraper.batch_history.psycopg2.connect")
def test_run_batch_returns_0_when_nothing_to_process(mock_pg, mock_discover):
    from scraper.batch_history import run_batch

    rc = run_batch(CONFIG, max_workers=5)
    assert rc == 0


@patch("scraper.batch_history.scrape_article_urls", side_effect=Exception("site down"))
def test_run_batch_returns_0_when_all_pages_fail_to_scrape(mock_scrape):
    from scraper.batch_history import run_batch

    rc = run_batch(CONFIG, start_page=2, end_page=1, max_workers=1)
    assert rc == 0
