"""Live incremental scraper: walks the blog listing backward until it hits
an already-known article, then reprocesses every article in that range.

Replaces the old single-newest-article scrape, which silently dropped any
incident posted before the very latest one, and the old single-terminal-tool
agent loop, which could only ever write one alert row per run — UW edits a
single article in place as an incident develops (original post at the
bottom, updates prepended above it), so an already-known article can still
grow new blocks that need to be caught.

"Have we seen this URL" and "has this article changed since we last saw it"
are different questions: an incident's URL becomes known the moment its
original post is stored, but the article keeps growing after that. Every
article in the scanned range is checked against a SHA-256 hash of its raw
text recorded directly by this module after the last successful scrape (not
against what the LLM transcribed into raw_scraped_text — Claude can quietly
normalize punctuation, e.g. smart quotes to straight quotes, even when told
to copy verbatim, which makes that comparison unreliable). If the hash
matches, nothing has changed and the LLM is skipped entirely; otherwise the
full block-parsing agent loop runs, and the existing alerts.text_hash
UNIQUE constraint makes reprocessing of any already-stored blocks within a
changed article a safe no-op.
"""

import hashlib
import json
import os
import time

import anthropic
import psycopg2

from scraper.config import get_anthropic_client, get_model_name
from scraper.logging_config import setup_logging
from scraper.prompts import render_prompt
from scraper.tools.database import (
    build_upsert_alert_schema,
    find_incident_id_by_source_url,
    get_last_scraped_hash,
    known_source_urls,
    record_scrape_hash,
    upsert_alert,
)
from scraper.tools.geocode import build_geocode_address_schema, geocode_address
from scraper.tools.scrape import ScrapingError, scrape_article, scrape_article_urls

logger = setup_logging("scraper.live")

SYSTEM_PROMPT = render_prompt("system_prompt.j2")

DEFAULT_MAX_PAGES = 4

LIVE_TOOLS = [
    build_geocode_address_schema(
        "Geocode a street address or named campus location. Call when "
        "establishing a new incident's location, or when an update genuinely "
        "corrects/refines the existing incident's location (not narrative "
        "movement, e.g. suspect direction of travel)."
    ),
    build_upsert_alert_schema(
        "Insert or refine an alert. For a brand-new incident call with "
        "is_new_incident=true. For an already-known incident (its incident_id "
        "will be given in your context) call with is_new_incident=false and "
        "that incident_id for every block in this article."
    ),
]


def _discover_urls_to_process(db_conn, max_pages: int = DEFAULT_MAX_PAGES) -> list:
    """Walk listing pages newest-first, expanding while every URL seen so far
    is unknown, stopping once a page contains at least one already-known URL.

    This is inherently sequential (each page's decision depends on the
    last) — unlike the batch importer's concurrent full-history discovery,
    do not thread it.

    Returns article URLs to process this cycle, oldest-first overall (the
    oldest scanned page first, each page's own newest-first listing reversed)
    so per-article processing follows the same chronological convention the
    batch importer uses.
    """
    pages = []
    for page_num in range(1, max_pages + 1):
        urls = scrape_article_urls(page_num)
        if not urls:
            break
        pages.append(urls)
        if known_source_urls(db_conn, urls):
            break
    else:
        logger.warning("page_scan_cap_reached", extra={"max_pages": max_pages})

    ordered = []
    for urls in reversed(pages):
        ordered.extend(reversed(urls))
    return ordered


def _dispatch(name, inputs, db_conn, config, dry_run):
    if name == "geocode_address":
        return geocode_address(inputs["address"], config["GOOGLE_MAPS_API_KEY"])
    if name == "upsert_alert":
        if dry_run:
            logger.info("dry_run_would_write", extra={"inputs": inputs})
            return {"status": "dry_run", "incident_id": 0}
        result = upsert_alert(db_conn, inputs)
        if result["status"] == "inserted":
            logger.info(
                "insert_success",
                extra={
                    "incident_id": result.get("incident_id"),
                    "alert_id": result.get("alert_id"),
                },
            )
        else:
            logger.warning(
                "duplicate_blocked", extra={"text_hash": result.get("text_hash")}
            )
        return result
    raise ValueError(f"Unknown tool: {name}")


def _process_live_article(url: str, config: dict, db_conn) -> dict:
    """Run the LLM agent for one article, known or unseen.

    If the article's current raw-text hash matches the hash recorded after
    the last successful scrape of this incident, returns "no_change"
    immediately without calling the LLM at all. Otherwise parses the article
    into alert blocks and calls upsert_alert once per block, looping until
    end_turn — same non-terminal pattern as the batch importer's
    run_batch_agent. Unlike batch, zero upsert_alert calls is a normal
    outcome ("no_change"), not an error: the article may have changed in a
    way that turned out not to need any new alert rows (e.g. a
    duplicate-detected re-attempt).

    Returns a summary dict with keys:
        status:           "inserted" | "duplicate" | "no_change" | "dry_run" | "error"
        alerts_inserted:  number of alert rows successfully inserted
        alerts_duplicate: number skipped due to text_hash collision
    """
    dry_run = os.environ.get("DRY_RUN", "").lower() == "true"

    try:
        article = scrape_article(url)
    except ScrapingError as e:
        logger.error("article_scrape_failed", extra={"url": url, "error": str(e)})
        return {
            "status": "error",
            "error": str(e),
            "alerts_inserted": 0,
            "alerts_duplicate": 0,
        }

    fresh_hash = hashlib.sha256(article["raw_text"].encode()).hexdigest()
    incident_id = find_incident_id_by_source_url(db_conn, url)

    if incident_id is not None:
        if get_last_scraped_hash(db_conn, incident_id) == fresh_hash:
            logger.info(
                "article_unchanged_skipped",
                extra={"url": url, "incident_id": incident_id},
            )
            return {"status": "no_change", "alerts_inserted": 0, "alerts_duplicate": 0}

    client = get_anthropic_client(config)
    model = get_model_name(config)

    if incident_id is not None:
        incident_context = (
            f"Existing incident check: this exact URL has already been ingested "
            f"as incident_id={incident_id}. You do NOT know which blocks in this "
            f"article are already stored — do not guess. Call upsert_alert with "
            f"is_new_incident=false and this incident_id for EVERY alert block "
            f"you parse from the article below, including the original post "
            f"block, even ones you suspect are already recorded. A block "
            f"that's already stored is automatically and harmlessly rejected by "
            f"the database (duplicate text is detected there, not by you) — "
            f"there is no cost to attempting one that turns out to be a repeat, "
            f"but a genuinely new block you skip will be permanently missed."
        )
    else:
        incident_context = (
            "Existing incident check: this URL has never been ingested. Use "
            "is_new_incident=true for the original post block — the response "
            "includes incident_id — then that incident_id for any subsequent "
            "update blocks in the same article."
        )

    messages = [
        {
            "role": "user",
            "content": (
                f"{incident_context}\n\n"
                "Parse and store this UW emergency alert article.\n\n"
                f"Article text:\n{article['raw_text']}\n\n"
                f"Source URL: {article.get('article_url', url)}\n"
                f"Scraped at: {article['scraped_at']}"
            ),
        }
    ]

    upsert_results = []

    try:
        while True:
            for attempt in range(3):
                try:
                    response = client.messages.create(
                        model=model,
                        max_tokens=4096,
                        system=SYSTEM_PROMPT,
                        tools=LIVE_TOOLS,
                        messages=messages,
                    )
                    break
                except anthropic.APIError as e:
                    if attempt == 2:
                        logger.error("claude_api_failed", extra={"error": str(e)})
                        return {
                            "status": "error",
                            "error": str(e),
                            "alerts_inserted": 0,
                            "alerts_duplicate": 0,
                        }
                    wait = 2 ** (attempt + 1)
                    time.sleep(wait)

            if response.stop_reason == "end_turn":
                break

            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    logger.info("tool_call", extra={"tool": block.name})
                    result = _dispatch(
                        block.name, block.input, db_conn, config, dry_run
                    )
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result),
                        }
                    )
                    if block.name == "upsert_alert":
                        upsert_results.append(result)

            if not tool_results:
                logger.warning(
                    "agent_returned_tool_use_with_no_tool_blocks",
                    extra={"url": url},
                )
                return {
                    "status": "error",
                    "error": "tool_use stop_reason with no tool_use blocks",
                    "alerts_inserted": 0,
                    "alerts_duplicate": 0,
                }

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        inserted = sum(1 for r in upsert_results if r.get("status") == "inserted")
        duplicate = sum(1 for r in upsert_results if r.get("status") == "duplicate")
        dry = sum(1 for r in upsert_results if r.get("status") == "dry_run")

        if dry:
            status = "dry_run"
        elif inserted:
            status = "inserted"
        elif duplicate:
            status = "duplicate"
        else:
            status = "no_change"

        if not dry_run:
            resolved_incident_id = incident_id or next(
                (
                    r.get("incident_id")
                    for r in upsert_results
                    if r.get("status") == "inserted"
                ),
                None,
            )
            if resolved_incident_id is not None:
                record_scrape_hash(db_conn, resolved_incident_id, fresh_hash)

        logger.info(
            "article_complete",
            extra={
                "url": url,
                "alerts_inserted": inserted,
                "alerts_duplicate": duplicate,
            },
        )
        return {
            "status": status,
            "alerts_inserted": inserted,
            "alerts_duplicate": duplicate,
        }

    except Exception as e:
        logger.error("live_agent_error", extra={"url": url, "error": str(e)})
        return {
            "status": "error",
            "error": str(e),
            "alerts_inserted": 0,
            "alerts_duplicate": 0,
        }


def run_live_discovery(config: dict) -> int:
    """Discover articles since the last cycle and process each one.

    Returns 0 on success or partial success; 1 only if nothing was inserted
    and there were errors (indicating a systemic failure).
    """
    db_conn = psycopg2.connect(config["DATABASE_URL"])
    stats = {
        "urls_found": 0,
        "inserted": 0,
        "duplicates": 0,
        "no_change": 0,
        "errors": 0,
    }
    try:
        urls = _discover_urls_to_process(db_conn)
        stats["urls_found"] = len(urls)
        if not urls:
            logger.info("nothing_to_process")
            return 0

        for url in urls:
            result = _process_live_article(url, config, db_conn)
            status = result.get("status", "error")
            if status in ("inserted", "duplicate", "dry_run"):
                stats["inserted"] += result.get("alerts_inserted", 0)
                stats["duplicates"] += result.get("alerts_duplicate", 0)
            elif status == "no_change":
                stats["no_change"] += 1
            else:
                stats["errors"] += 1
                logger.error(
                    "article_failed",
                    extra={"url": url, "error": result.get("error", "unknown")},
                )

        logger.info("live_discovery_complete", extra=stats)
        return 1 if stats["inserted"] == 0 and stats["errors"] > 0 else 0
    finally:
        db_conn.close()
