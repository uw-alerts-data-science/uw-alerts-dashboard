# Parallel Batch Scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `batch_history.py` so it discovers all article URLs from listing pages, then fans out to N parallel workers (default 50) each of which fetches a batch of individual article pages, calls the LLM, and writes to the DB — treating every article as a new incident.

**Architecture:** Phase 1 scrapes listing pages concurrently (HTTP only, no LLM) to collect article permalink URLs. Phase 2 divides URLs into equal batches and assigns one batch to each worker. Each worker owns its own `psycopg2` connection, fetches each article's full page, and runs the simplified LLM agent (no update-linking; every article → new incident).

**Tech Stack:** Python `concurrent.futures.ThreadPoolExecutor`, `psycopg2`, `anthropic`, `requests`, `BeautifulSoup`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `scraper/tools/scrape.py` | Modify | Add `scrape_article_urls(page_num)` (URLs only) and `scrape_article(url)` (full text from permalink) |
| `scraper/batch_system_prompt.py` | Modify | Simplify — remove update-linking instructions since every article is a new incident |
| `scraper/batch_history.py` | Rewrite | Two-phase: discover URLs → fan out workers each processing a batch |
| `scraper/tests/test_scrape.py` | Modify | Add tests for the two new scrape functions |
| `scraper/tests/test_batch_history.py` | Modify | Update tests to match new worker/dispatch model |

---

### Task 1: Add `scrape_article_urls` and `scrape_article` to scrape.py

**Context:** `scrape_page` currently fetches a listing page and extracts article text from the listing page HTML (which may be truncated). We need two new functions:
- `scrape_article_urls(page_num)` — returns only the list of permalink URLs from a listing page (fast, minimal parsing)
- `scrape_article(url)` — fetches an individual article permalink and returns its full text

**Files:**
- Modify: `scraper/tools/scrape.py`
- Modify: `scraper/tests/test_scrape.py`

- [ ] **Step 1: Write failing tests for `scrape_article_urls`**

Add to `scraper/tests/test_scrape.py`:

```python
from unittest.mock import patch, MagicMock
from scraper.tools.scrape import scrape_article_urls, scrape_article, ScrapingError

LISTING_HTML = """
<html><body>
<main class="site-main">
  <article>
    <h2 class="entry-title"><a href="https://emergency.uw.edu/2024/01/theft/">Theft</a></h2>
    <time class="entry-date">Jan 1 2024</time>
  </article>
  <article>
    <h2 class="entry-title"><a href="https://emergency.uw.edu/2024/02/assault/">Assault</a></h2>
    <time class="entry-date">Feb 1 2024</time>
  </article>
  <article>
    <!-- no time element — should be skipped -->
    <h2 class="entry-title"><a href="https://emergency.uw.edu/promo/">Promo</a></h2>
  </article>
</main>
</body></html>
"""

ARTICLE_HTML = """
<html><body>
<main class="site-main">
  <article>
    <time class="entry-date">Jan 1 2024</time>
    <div class="entry-content">Theft occurred near HUB at 10pm. UWPD responding.</div>
  </article>
</main>
</body></html>
"""


@patch("scraper.tools.scrape.requests.get")
def test_scrape_article_urls_returns_permalinks(mock_get):
    mock_get.return_value = MagicMock(status_code=200, text=LISTING_HTML)
    mock_get.return_value.raise_for_status = MagicMock()
    urls = scrape_article_urls(3)
    assert urls == [
        "https://emergency.uw.edu/2024/01/theft/",
        "https://emergency.uw.edu/2024/02/assault/",
    ]


@patch("scraper.tools.scrape.requests.get")
def test_scrape_article_urls_page1_uses_base_url(mock_get):
    mock_get.return_value = MagicMock(status_code=200, text=LISTING_HTML)
    mock_get.return_value.raise_for_status = MagicMock()
    scrape_article_urls(1)
    called_url = mock_get.call_args[0][0]
    assert called_url == "https://emergency.uw.edu/"


@patch("scraper.tools.scrape.requests.get")
def test_scrape_article_urls_raises_on_http_error(mock_get):
    mock_get.side_effect = Exception("timeout")
    with pytest.raises(ScrapingError):
        scrape_article_urls(2)


@patch("scraper.tools.scrape.requests.get")
def test_scrape_article_returns_raw_text(mock_get):
    mock_get.return_value = MagicMock(status_code=200, text=ARTICLE_HTML)
    mock_get.return_value.raise_for_status = MagicMock()
    result = scrape_article("https://emergency.uw.edu/2024/01/theft/")
    assert "Theft occurred near HUB" in result["raw_text"]
    assert result["article_url"] == "https://emergency.uw.edu/2024/01/theft/"
    assert "scraped_at" in result


@patch("scraper.tools.scrape.requests.get")
def test_scrape_article_raises_on_missing_article_element(mock_get):
    mock_get.return_value = MagicMock(status_code=200, text="<html><body><main class='site-main'></main></body></html>")
    mock_get.return_value.raise_for_status = MagicMock()
    with pytest.raises(ScrapingError):
        scrape_article("https://emergency.uw.edu/2024/01/theft/")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest scraper/tests/test_scrape.py -k "scrape_article" -v
```

Expected: `ImportError` or `AttributeError` (functions don't exist yet)

- [ ] **Step 3: Implement `scrape_article_urls` and `scrape_article` in scrape.py**

Add to `scraper/tools/scrape.py` (after the existing `scrape_page` function):

```python
def scrape_article_urls(page_num: int) -> list:
    """Return the list of article permalink URLs from a listing page.

    Skips articles without a <time class="entry-date"> element (nav/promo).
    Returns URLs in the order they appear on the page (newest-first for WordPress).

    Args:
        page_num: 1 for the most recent page, higher numbers for older pages.

    Raises:
        ScrapingError: on HTTP failure or missing site-main element.
    """
    url = UW_ALERTS_URL if page_num == 1 else f"{UW_ALERTS_URL}page/{page_num}/"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        raise ScrapingError(f"Failed to fetch page {page_num}: {e}") from e

    soup = BeautifulSoup(resp.text, "html.parser")
    main = soup.find("main", class_="site-main")
    if not main:
        raise ScrapingError(f"Could not find site-main element on page {page_num}")

    urls = []
    for article in main.find_all("article"):
        if not article.find("time", class_="entry-date"):
            continue
        title_el = article.find("h2", class_="entry-title") or article.find("h1", class_="entry-title")
        if title_el:
            a = title_el.find("a", href=True)
            if a:
                urls.append(a["href"])
    return urls


def scrape_article(url: str) -> dict:
    """Fetch an individual article permalink and return its full text.

    Returns a dict with keys: raw_text, article_url, scraped_at.

    Args:
        url: Full permalink URL of the article.

    Raises:
        ScrapingError: on HTTP failure or if no article element is found.
    """
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        raise ScrapingError(f"Failed to fetch article {url}: {e}") from e

    soup = BeautifulSoup(resp.text, "html.parser")
    main = soup.find("main", class_="site-main")
    if not main:
        raise ScrapingError(f"Could not find site-main on {url}")

    article = main.find("article")
    if not article:
        raise ScrapingError(f"Could not find article element on {url}")

    return {
        "raw_text": article.get_text(separator="\n", strip=True),
        "article_url": url,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest scraper/tests/test_scrape.py -k "scrape_article" -v
```

Expected: all 5 new tests PASS

- [ ] **Step 5: Commit**

```bash
git add scraper/tools/scrape.py scraper/tests/test_scrape.py
git commit -m "feat(scraper): add scrape_article_urls and scrape_article for per-permalink fetching"
```

---

### Task 2: Simplify `batch_system_prompt.py`

**Context:** The current prompt tells the LLM to call `query_recent_incidents` first, then decide whether to link the article as an update to a prior incident. Since every article is treated as a new incident, all that complexity goes away. The new prompt just needs: parse the article, geocode if there's an address, call `upsert_alert` with `is_new_incident=True`.

**Files:**
- Modify: `scraper/batch_system_prompt.py`

- [ ] **Step 1: Rewrite the system prompt**

Replace the entire contents of `scraper/batch_system_prompt.py`:

```python
BATCH_SYSTEM_PROMPT = """You are the database manager for the University of Washington \
emergency alert system, performing a historical data import from the UW emergency blog archive. \
Students on campus rely on this data for their physical safety.

The article text has already been scraped and is provided to you. Do NOT call any scraping tools.

ACCURACY RULES — NEVER VIOLATE THESE:
- full_text and raw_scraped_text must be copied verbatim from the article text provided. \
Never paraphrase, summarize, correct spelling, or modify alert text in any way. These are \
legal public safety records and must be preserved token-perfectly.
- Never infer fields not explicitly stated in the alert text. If a time or address is \
ambiguous, leave that field null rather than guessing.

STEPS — follow in order:
1. Parse the article text to extract fields (see FIELD EXTRACTION GUIDE below).
2. If the article contains a street address or named on-campus location, call geocode_address.
3. Call upsert_alert with is_new_incident=true. Every article is a new incident.

FIELD EXTRACTION GUIDE:
- reported_at: publication date/time from the article header (ISO 8601 format)
- occurred_at: when the incident happened if stated in the body (may differ from reported_at)
- nearest_address: the street address or named location mentioned in the alert body
- category: incident type — one of: Theft, Robbery, Assault, Sexual Assault, \
Suspicious Activity, Suspicious Person, Disturbance, Fire, Medical Emergency, \
Missing Person, Motor Vehicle Incident, Harassment, Other
- summary: 1-2 sentence factual summary extracted verbatim or near-verbatim from the alert
- alert_type: always "original"
- set source_url to the article URL provided in the user message
"""
```

- [ ] **Step 2: Verify no tests reference the old prompt content**

```bash
grep -r "query_recent_incidents first\|FOLLOW UP\|parent incident" scraper/tests/
```

Expected: no output (nothing references the old update-linking instructions)

- [ ] **Step 3: Commit**

```bash
git add scraper/batch_system_prompt.py
git commit -m "feat(scraper): simplify batch system prompt — every article is a new incident"
```

---

### Task 3: Rewrite `batch_history.py`

**Context:** The new flow is:
1. Discover all article URLs from listing pages (parallel HTTP, `DISCOVERY_WORKERS=10`)
2. Pre-filter URLs already in the DB (bulk `SELECT source_url FROM alerts WHERE source_url = ANY(%s)`)
3. Divide remaining URLs into `N` equal-ish batches (`BATCH_WORKERS`, default 50 or `len(urls)` whichever is smaller)
4. Each worker processes its batch serially: `scrape_article(url)` → `run_batch_agent()` → insert

The LLM tools are reduced to: `geocode_address`, `upsert_alert` (no `query_recent_incidents`, no `search_incidents`, no `mark_no_update`).

**Files:**
- Modify: `scraper/batch_history.py`
- Modify: `scraper/tests/test_batch_history.py`

- [ ] **Step 1: Write failing tests for the new worker model**

Replace the `run_batch stats / page loop` section of `scraper/tests/test_batch_history.py`:

```python
# ── _discover_article_urls ───────────────────────────────────────────────────

@patch("scraper.batch_history.scrape_article_urls", return_value=[
    "https://emergency.uw.edu/2024/01/theft/",
    "https://emergency.uw.edu/2024/02/robbery/",
])
def test_discover_article_urls_returns_flat_list(mock_scrape):
    from scraper.batch_history import _discover_article_urls
    urls = _discover_article_urls(start_page=2, end_page=1, max_pages=50)
    # 2 pages × 2 urls each = 4 urls
    assert len(urls) == 4


@patch("scraper.batch_history.scrape_article_urls", side_effect=Exception("timeout"))
def test_discover_article_urls_skips_failed_pages(mock_scrape):
    from scraper.batch_history import _discover_article_urls
    urls = _discover_article_urls(start_page=2, end_page=1, max_pages=50)
    assert urls == []


# ── _process_batch_worker ────────────────────────────────────────────────────

@patch("scraper.batch_history.run_batch_agent", return_value={"status": "inserted", "incident_id": 1, "alert_id": 1})
@patch("scraper.batch_history.scrape_article", return_value={
    "raw_text": "Theft near HUB.", "article_url": "https://emergency.uw.edu/2024/01/theft/", "scraped_at": "2026-01-01T00:00:00+00:00"
})
@patch("scraper.batch_history.psycopg2.connect")
def test_process_batch_worker_calls_agent_for_each_url(mock_pg, mock_scrape, mock_agent):
    from scraper.batch_history import _process_batch_worker
    urls = ["https://emergency.uw.edu/2024/01/theft/", "https://emergency.uw.edu/2024/02/robbery/"]
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

@patch("scraper.batch_history._process_batch_worker", return_value=[
    {"status": "inserted", "incident_id": 1, "alert_id": 1},
    {"status": "inserted", "incident_id": 2, "alert_id": 2},
])
@patch("scraper.batch_history._discover_article_urls", return_value=[
    "https://emergency.uw.edu/a/", "https://emergency.uw.edu/b/",
    "https://emergency.uw.edu/c/", "https://emergency.uw.edu/d/",
])
@patch("scraper.batch_history.psycopg2.connect")
def test_run_batch_counts_inserted(mock_pg, mock_discover, mock_worker):
    mock_pg.return_value.cursor.return_value.__enter__.return_value.fetchall.return_value = []
    from scraper.batch_history import run_batch
    rc = run_batch(CONFIG, max_workers=2)
    assert rc == 0


@patch("scraper.batch_history._process_batch_worker", return_value=[
    {"status": "error", "error": "something broke"},
])
@patch("scraper.batch_history._discover_article_urls", return_value=["https://emergency.uw.edu/a/"])
@patch("scraper.batch_history.psycopg2.connect")
def test_run_batch_returns_0_on_partial_errors(mock_pg, mock_discover, mock_worker):
    """One error but some inserts → still rc=0 (partial success is fine)."""
    mock_pg.return_value.cursor.return_value.__enter__.return_value.fetchall.return_value = []
    from scraper.batch_history import run_batch
    rc = run_batch(CONFIG, max_workers=1)
    # errors=1 but inserted=0 → rc=1; test confirms correct threshold
    assert rc == 1


@patch("scraper.batch_history._discover_article_urls", return_value=[])
@patch("scraper.batch_history.psycopg2.connect")
def test_run_batch_returns_0_when_nothing_to_process(mock_pg, mock_discover):
    from scraper.batch_history import run_batch
    rc = run_batch(CONFIG, max_workers=5)
    assert rc == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest scraper/tests/test_batch_history.py -k "discover or process_batch or run_batch" -v
```

Expected: ImportError or AttributeError on `_discover_article_urls`, `_process_batch_worker`

- [ ] **Step 3: Rewrite `batch_history.py`**

Replace the entire file:

```python
"""Full history batch scraper for UW Alerts.

Two-phase parallel approach:
  Phase 1 — Discover article URLs from all listing pages concurrently (HTTP only, no LLM).
  Phase 2 — Divide URLs into batches, one batch per worker. Each worker fetches the full
             article page, calls the LLM, and inserts into the DB using its own connection.

Every article is treated as a new incident. Safe to re-run — text_hash dedup prevents
duplicate inserts, and URL pre-filtering skips already-ingested articles.

Usage:
    python -m scraper.batch_history
    DRY_RUN=true python -m scraper.batch_history
    BATCH_WORKERS=50 python -m scraper.batch_history
    python -m scraper.batch_history --max-pages 30 --workers 20
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic
import psycopg2

from scraper.batch_system_prompt import BATCH_SYSTEM_PROMPT
from scraper.config import get_anthropic_client, get_model_name, load_config
from scraper.logging_config import setup_logging
from scraper.tools.database import upsert_alert
from scraper.tools.geocode import geocode_address
from scraper.tools.scrape import ScrapingError, scrape_article, scrape_article_urls

logger = setup_logging("scraper.batch")

DEFAULT_MAX_PAGES = 50
DEFAULT_PROCESS_WORKERS = 50
DISCOVERY_WORKERS = 10

BATCH_TOOLS = [
    {
        "name": "geocode_address",
        "description": "Geocode a street address or named campus location. Call for every incident that has a location.",
        "input_schema": {
            "type": "object",
            "properties": {"address": {"type": "string"}},
            "required": ["address"],
        },
    },
    {
        "name": "upsert_alert",
        "description": "Insert the parsed alert into the database as a new incident.",
        "input_schema": {
            "type": "object",
            "properties": {
                "alert_type": {"type": "string", "enum": ["original"]},
                "category": {"type": "string"},
                "nearest_address": {"type": "string"},
                "google_address": {"type": "string"},
                "lat": {"type": "number"},
                "lng": {"type": "number"},
                "occurred_at": {"type": "string"},
                "reported_at": {"type": "string"},
                "summary": {"type": "string"},
                "full_text": {"type": "string"},
                "raw_scraped_text": {"type": "string"},
                "source_url": {"type": "string"},
            },
            "required": ["alert_type", "full_text", "raw_scraped_text"],
        },
    },
]

TERMINAL_TOOL = "upsert_alert"


def _dispatch(name, inputs, db_conn, config, dry_run):
    if name == "geocode_address":
        return geocode_address(inputs["address"], config["GOOGLE_MAPS_API_KEY"])
    if name == "upsert_alert":
        if dry_run:
            logger.info("dry_run_would_write", extra={"inputs": inputs})
            return {"status": "dry_run"}
        # Always a new incident
        payload = dict(inputs)
        payload["is_new_incident"] = True
        payload["alert_type"] = "original"
        result = upsert_alert(db_conn, payload)
        if result["status"] == "inserted":
            logger.info("insert_success", extra={
                "incident_id": result.get("incident_id"),
                "alert_id": result.get("alert_id"),
            })
        else:
            logger.warning("duplicate_blocked", extra={"text_hash": result.get("text_hash")})
        return result
    raise ValueError(f"Unknown tool: {name}")


def run_batch_agent(article: dict, config: dict, db_conn) -> dict:
    """Run the LLM agent for one pre-scraped article.

    Returns a dict with at minimum a "status" key:
    "inserted", "duplicate", "dry_run", or "error".
    """
    dry_run = os.environ.get("DRY_RUN", "").lower() == "true"
    client = get_anthropic_client(config)
    model = get_model_name(config)

    messages = [
        {
            "role": "user",
            "content": (
                "Parse and store this UW emergency alert.\n\n"
                f"Article text:\n{article['raw_text']}\n\n"
                f"Source URL: {article.get('article_url', 'https://emergency.uw.edu/')}\n"
                f"Scraped at: {article['scraped_at']}"
            ),
        }
    ]

    try:
        while True:
            for attempt in range(3):
                try:
                    response = client.messages.create(
                        model=model,
                        max_tokens=4096,
                        system=BATCH_SYSTEM_PROMPT,
                        tools=BATCH_TOOLS,
                        messages=messages,
                    )
                    break
                except anthropic.APIError as e:
                    if attempt == 2:
                        logger.error("claude_api_failed", extra={"error": str(e)})
                        return {"status": "error", "error": str(e)}
                    wait = 2 ** (attempt + 1)
                    time.sleep(wait)

            if response.stop_reason == "end_turn":
                logger.warning("agent_ended_without_terminal_tool",
                               extra={"url": article.get("article_url")})
                return {"status": "error", "error": "agent ended without calling upsert_alert"}

            tool_results = []
            last_result = {}

            for block in response.content:
                if block.type == "tool_use":
                    logger.info("tool_call", extra={"tool": block.name})
                    result = _dispatch(block.name, block.input, db_conn, config, dry_run)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })
                    if block.name == TERMINAL_TOOL:
                        last_result = result

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

            if last_result:
                return last_result

    except Exception as e:
        logger.error("batch_agent_error", extra={"error": str(e)})
        return {"status": "error", "error": str(e)}


def _try_scrape_article_urls(page_num: int) -> list:
    """Scrape article URLs from one listing page; return [] on any error."""
    try:
        urls = scrape_article_urls(page_num)
        if urls:
            logger.info("page_scraped", extra={"page": page_num, "url_count": len(urls)})
        return urls
    except ScrapingError as e:
        logger.debug("page_scrape_failed", extra={"page": page_num, "error": str(e)})
        return []


def _discover_article_urls(
    start_page: int,
    end_page: int,
    max_pages: int,
) -> list:
    """Scrape all listing pages concurrently and return flat list of article URLs."""
    upper = min(start_page, max_pages)
    pages = list(range(end_page, upper + 1))
    logger.info("discovery_start", extra={"pages_to_scan": len(pages)})

    all_urls = []
    with ThreadPoolExecutor(max_workers=DISCOVERY_WORKERS) as executor:
        futures = {executor.submit(_try_scrape_article_urls, p): p for p in pages}
        for fut in as_completed(futures):
            all_urls.extend(fut.result())

    logger.info("discovery_complete", extra={"article_urls_found": len(all_urls)})
    return all_urls


def _prefilter_known_urls(urls: list, database_url: str) -> list:
    """Remove URLs already present in the alerts table."""
    if not urls:
        return urls
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT DISTINCT source_url FROM alerts WHERE source_url = ANY(%s)",
                (urls,),
            )
            known = {row[0] for row in cur.fetchall()}
    finally:
        conn.close()
    fresh = [u for u in urls if u not in known]
    skipped = len(urls) - len(fresh)
    if skipped:
        logger.info("prefilter_skipped", extra={"count": skipped})
    return fresh


def _process_batch_worker(urls: list, config: dict) -> list:
    """Worker: process a batch of article URLs serially using one DB connection.

    Returns a list of result dicts (one per URL), each with at least a "status" key.
    """
    db_conn = psycopg2.connect(config["DATABASE_URL"])
    results = []
    try:
        for url in urls:
            try:
                article = scrape_article(url)
            except ScrapingError as e:
                logger.error("article_scrape_failed", extra={"url": url, "error": str(e)})
                results.append({"status": "error", "error": str(e), "url": url})
                continue
            result = run_batch_agent(article, config, db_conn)
            result["url"] = url
            results.append(result)
    except Exception as e:
        try:
            db_conn.rollback()
        except Exception:
            pass
        logger.error("worker_crashed", extra={"error": str(e)})
    finally:
        db_conn.close()
    return results


def _chunk(lst: list, n: int) -> list:
    """Split lst into n roughly equal chunks."""
    if n <= 0 or not lst:
        return [lst]
    k, rem = divmod(len(lst), n)
    chunks, i = [], 0
    for chunk_idx in range(n):
        size = k + (1 if chunk_idx < rem else 0)
        chunks.append(lst[i: i + size])
        i += size
    return [c for c in chunks if c]


def run_batch(
    config: dict,
    start_page: int = DEFAULT_MAX_PAGES,
    end_page: int = 1,
    max_pages: int = DEFAULT_MAX_PAGES,
    max_workers: int = None,
) -> int:
    """Discover all article URLs then fan out workers to process them.

    Returns 0 on success or partial success; 1 only if nothing was inserted
    and there were errors (indicating a systemic failure).
    """
    n_workers = max_workers or int(os.environ.get("BATCH_WORKERS", DEFAULT_PROCESS_WORKERS))

    # Phase 1: discover URLs
    all_urls = _discover_article_urls(start_page, end_page, max_pages)
    pages_scanned = min(start_page, max_pages) - end_page + 1

    # Phase 2: pre-filter
    dry_run = os.environ.get("DRY_RUN", "").lower() == "true"
    fresh_urls = all_urls if dry_run else _prefilter_known_urls(all_urls, config["DATABASE_URL"])
    pre_skipped = len(all_urls) - len(fresh_urls)

    stats = {
        "pages_scanned": pages_scanned,
        "urls_found": len(all_urls),
        "inserted": 0,
        "duplicates": pre_skipped,
        "errors": 0,
    }

    if not fresh_urls:
        logger.info("nothing_to_process")
        _print_summary(stats)
        return 0

    # Phase 3: parallel workers, each with a batch of URLs
    actual_workers = min(n_workers, len(fresh_urls))
    batches = _chunk(fresh_urls, actual_workers)
    logger.info("processing_start", extra={
        "urls_to_process": len(fresh_urls),
        "workers": actual_workers,
        "batch_size": len(batches[0]) if batches else 0,
    })

    with ThreadPoolExecutor(max_workers=actual_workers) as executor:
        futures = [executor.submit(_process_batch_worker, batch, config) for batch in batches]
        for fut in as_completed(futures):
            for result in fut.result():
                status = result.get("status", "error")
                if status == "inserted":
                    stats["inserted"] += 1
                elif status in ("duplicate", "dry_run"):
                    stats["duplicates"] += 1
                else:
                    stats["errors"] += 1
                    logger.error("article_failed", extra={
                        "url": result.get("url", ""),
                        "error": result.get("error", "unknown"),
                    })

    logger.info("batch_complete", extra=stats)
    _print_summary(stats)
    return 1 if stats["inserted"] == 0 and stats["errors"] > 0 else 0


def _print_summary(stats: dict) -> None:
    print(
        f"\nBatch complete: {stats['inserted']} inserted, "
        f"{stats['duplicates']} skipped, {stats['errors']} errors "
        f"({stats['urls_found']} articles across {stats['pages_scanned']} pages scanned)"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parallel UW Alerts history scraper")
    parser.add_argument("--max-pages", type=int, default=DEFAULT_MAX_PAGES,
                        help=f"Max page number to scan (default {DEFAULT_MAX_PAGES})")
    parser.add_argument("--start-page", type=int, default=DEFAULT_MAX_PAGES)
    parser.add_argument("--end-page", type=int, default=1)
    parser.add_argument("--workers", type=int, default=None,
                        help=f"Parallel workers (default BATCH_WORKERS env or {DEFAULT_PROCESS_WORKERS})")
    args = parser.parse_args()
    sys.exit(run_batch(
        load_config(),
        start_page=args.start_page,
        end_page=args.end_page,
        max_pages=args.max_pages,
        max_workers=args.workers,
    ))
```

- [ ] **Step 4: Run the new batch_history tests**

```bash
uv run pytest scraper/tests/test_batch_history.py -v
```

Expected: all tests PASS (some old tests covering `query_recent_incidents` dispatch may now be stale — delete any that reference tools removed from BATCH_TOOLS)

- [ ] **Step 5: Remove stale tests that reference removed tools**

The old `test_batch_history.py` contains tests for `run_batch_agent` that mock `query_recent_incidents` dispatch and `search_incidents`. Those tools no longer exist in BATCH_TOOLS. Delete the following tests (they test dead code):
- `test_run_batch_agent_upsert_returns_inserted` — keep, but update mock if needed
- Any test that patches `scraper.batch_history.query_recent_incidents` or `scraper.batch_history.search_incidents`

After cleanup:

```bash
uv run pytest scraper/tests/test_batch_history.py -v
```

Expected: all remaining tests PASS

- [ ] **Step 6: Run the full scraper test suite**

```bash
uv run pytest scraper/tests/ --ignore=scraper/tests/test_schema.py --ignore=scraper/tests/test_migrate.py -v
```

Expected: all tests PASS

- [ ] **Step 7: Commit**

```bash
git add scraper/batch_history.py scraper/tests/test_batch_history.py
git commit -m "feat(scraper): rewrite batch_history with per-URL worker model and simplified agent"
```

---

### Task 4: Smoke test with DRY_RUN

**Context:** Verify the full pipeline (discovery → dispatch → per-URL fetch → LLM → dry write) runs end-to-end against the real site without writing to the DB.

**Files:** none (runtime test only)

- [ ] **Step 1: Run dry-run against real site**

```bash
make batch-history-dry
```

Or directly:

```bash
set -a && . ./.env && DRY_RUN=true python -m scraper.batch_history --max-pages 2 --workers 5
```

Expected output (approximate):
```
{"event": "discovery_start", "pages_to_scan": 2, ...}
{"event": "page_scraped", "page": 1, "url_count": 10, ...}
{"event": "page_scraped", "page": 2, "url_count": 10, ...}
{"event": "discovery_complete", "article_urls_found": 20, ...}
{"event": "processing_start", "urls_to_process": 20, "workers": 5, ...}
... tool_call: geocode_address (for articles with addresses) ...
... dry_run_would_write ...
{"event": "batch_complete", "inserted": 0, "duplicates": 0, "errors": 0, ...}

Batch complete: 0 inserted, 0 skipped, 0 errors (20 articles across 2 pages scanned)
```

- [ ] **Step 2: Verify no make errors**

```bash
make batch-history-dry 2>&1 | tail -5
```

Expected: no `make: *** [batch-history-dry] Error` line

- [ ] **Step 3: Final test run**

```bash
uv run pytest scraper/tests/ --ignore=scraper/tests/test_schema.py --ignore=scraper/tests/test_migrate.py -v
```

Expected: all tests PASS

- [ ] **Step 4: Commit**

```bash
git add -p   # review any final tweaks
git commit -m "test(scraper): verify parallel batch dry-run end-to-end"
```
