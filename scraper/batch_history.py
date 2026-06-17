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
    except Exception as e:
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
            except Exception as e:
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
