import json
import sys
import time

import anthropic
import psycopg2

from scraper.config import load_config
from scraper.logging_config import setup_logging
from scraper.system_prompt import SYSTEM_PROMPT
from scraper.tools.scrape import scrape_uw_blog, ScrapingError
from scraper.tools.database import query_recent_incidents, upsert_alert
from scraper.tools.geocode import geocode_address

logger = setup_logging()

TOOLS = [
    {"name": "scrape_uw_blog",
     "description": "Fetch the UW emergency alerts blog. Always call this first.",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "query_recent_incidents",
     "description": "Get N most recent incidents from DB to detect duplicates and match updates.",
     "input_schema": {"type": "object", "properties": {
         "limit": {"type": "integer", "default": 10}}, "required": []}},
    {"name": "geocode_address",
     "description": "Geocode a street address. Call only for new incidents.",
     "input_schema": {"type": "object", "properties": {
         "address": {"type": "string"}}, "required": ["address"]}},
    {"name": "upsert_alert",
     "description": "Insert alert. Creates incident+alert rows for new; alert only for updates.",
     "input_schema": {"type": "object", "properties": {
         "is_new_incident": {"type": "boolean"},
         "incident_id": {"type": "integer"},
         "alert_type": {"type": "string", "enum": ["original", "update"]},
         "category": {"type": "string"}, "nearest_address": {"type": "string"},
         "google_address": {"type": "string"}, "lat": {"type": "number"},
         "lng": {"type": "number"}, "occurred_at": {"type": "string"},
         "reported_at": {"type": "string"}, "summary": {"type": "string"},
         "full_text": {"type": "string"}, "raw_scraped_text": {"type": "string"}},
     "required": ["is_new_incident", "alert_type", "full_text", "raw_scraped_text"]}},
    {"name": "mark_no_update",
     "description": "Call when scraped content is already in DB. Ends the agent run.",
     "input_schema": {"type": "object", "properties": {
         "reason": {"type": "string"}}, "required": ["reason"]}},
]

TERMINAL_TOOLS = {"mark_no_update", "upsert_alert"}


def _dispatch(name, inputs, db_conn, config):
    if name == "scrape_uw_blog":
        return scrape_uw_blog()
    if name == "query_recent_incidents":
        return {"incidents": query_recent_incidents(db_conn, inputs.get("limit", 10))}
    if name == "geocode_address":
        return geocode_address(inputs["address"], config["GOOGLE_MAPS_API_KEY"])
    if name == "upsert_alert":
        result = upsert_alert(db_conn, inputs)
        if result["status"] == "inserted":
            logger.info("insert_success", extra={"incident_id": result.get("incident_id"),
                                                  "alert_id": result.get("alert_id")})
        else:
            logger.warning("duplicate_blocked", extra={"text_hash": result.get("text_hash")})
        return result
    if name == "mark_no_update":
        logger.info("no_update", extra={"reason": inputs.get("reason", "")})
        return {"status": "ok"}
    raise ValueError(f"Unknown tool: {name}")


def run_agent(config: dict) -> int:
    client = anthropic.Anthropic(api_key=config["ANTHROPIC_API_KEY"])
    db_conn = psycopg2.connect(config["DATABASE_URL"])
    messages = [{"role": "user", "content": "Check the UW alerts blog for new alerts and update the database."}]
    try:
        while True:
            for attempt in range(3):
                try:
                    response = client.messages.create(
                        model="claude-haiku-4-5-20251001", max_tokens=4096,
                        system=SYSTEM_PROMPT, tools=TOOLS, messages=messages)
                    break
                except anthropic.APIError as e:
                    if attempt == 2:
                        logger.error("claude_api_failed", extra={"error": str(e)})
                        return 1
                    wait = 2 ** (attempt + 1)
                    logger.warning("claude_api_retry", extra={"attempt": attempt + 1, "wait_seconds": wait})
                    time.sleep(wait)

            if response.stop_reason == "end_turn":
                logger.info("agent_complete", extra={"stop_reason": "end_turn"})
                break

            tool_results, called_terminal = [], False
            for block in response.content:
                if block.type == "tool_use":
                    logger.info("tool_call", extra={"tool": block.name})
                    result = _dispatch(block.name, block.input, db_conn, config)
                    tool_results.append({"type": "tool_result", "tool_use_id": block.id,
                                         "content": json.dumps(result)})
                    if block.name in TERMINAL_TOOLS:
                        called_terminal = True

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
            if called_terminal:
                break
        return 0
    except ScrapingError as e:
        logger.error("scrape_failed", extra={"error": str(e)})
        return 1
    except Exception as e:
        logger.error("agent_error", extra={"error": str(e)})
        return 1
    finally:
        db_conn.close()


if __name__ == "__main__":
    sys.exit(run_agent(load_config()))
