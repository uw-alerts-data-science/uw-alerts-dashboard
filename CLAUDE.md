# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Flask web application that visualizes University of Washington campus safety alerts on an interactive map. A Claude-based agentic scraper fetches alerts, geocodes them via Google Maps, and stores them to PostgreSQL. The Flask app queries Postgres and renders incidents as a Folium map with heatmap overlays.

## Environment Setup

```bash
uv sync       # installs all dependencies including dev tools
```

Requires a `.env` file in the root directory. Copy `.env.example` and fill in your values:
```
# Web app
OPENAI_API_KEY='...'
GOOGLE_MAPS_API_KEY='...'
MAPBOX_API_KEY='...'
DATABASE_URL='...'

# Scraper (direct Anthropic)
ANTHROPIC_API_KEY='...'
GOOGLE_MAPS_API_KEY='...'
DATABASE_URL='...'

# Scraper (Azure Anthropic — set USE_AZURE=true to activate)
USE_AZURE=true
AZURE_ANTHROPIC_BASE_URL='...'
AZURE_ANTHROPIC_API_KEY='...'
AZURE_ANTHROPIC_DEPLOYMENT='...'

# Optional model overrides for scraper
ANTHROPIC_HAIKU_MODEL='...'
ANTHROPIC_SONNET_MODEL='...'
```

## Commands

```bash
# Web app
cd uw-alert-web && uv run flask --app=uw-alert-web run   # http://127.0.0.1:5000

# Tests
uv run poe test           # web app tests with coverage
uv run poe test-scraper   # scraper tests (pytest)

# Single test file
cd uw-alert-web && uv run python -m unittest tests/test_parse_uw_alerts.py
pytest scraper/tests/test_agent.py -v

# Lint / format
uv run poe fmt            # ruff format + ruff check --fix
uv run poe lint           # check only, no writes

# Scraper (dry run — no DB writes)
DRY_RUN=true python -m scraper.scraper_agent

# CSV → Postgres migration (one-time)
python -m scraper.db.migrate
```

CI runs on Python 3.10 and 3.11 using uv. Ruff config is in `pyproject.toml` (`[tool.ruff]`); `E501`, `W291`, `W293` are disabled.

## Architecture

```
scraper/                      # Agentic scraper (runs independently of Flask)
  scraper_agent.py            # Claude tool-use agent — entry point
  config.py                   # Env loading; Anthropic client factory (direct or Azure)
  system_prompt.py            # Agent system prompt
  tools/
    scrape.py                 # BeautifulSoup fetch of UW Alerts blog
    geocode.py                # Google Maps geocoding
    database.py               # query_recent_incidents, upsert_alert (Postgres)
  db/
    migrate.py                # One-time CSV → Postgres migration
  tests/                      # pytest-based tests for all scraper modules

uw-alert-web/
  uw-alert-web.py             # Flask routes — no business logic
  db.py                       # query_incidents_as_dataframe() — reads from Postgres
  parse_uw_alerts/
    parse_uw_alerts.py        # Legacy GPT parser + scraper (kept for /fully_update route)
  visualization_manager/
    visualization_manager.py  # Folium map generation, marker attachment, heatmap
    process_seattle_streets.py # GeoDataFrame for Seattle street overlay
  tests/                      # unittest-based tests

data/
  uw_alerts_clean.csv         # Legacy primary store — still used by /fully_update route
  SeattleGISData/             # Seattle street GIS shapefiles

templates/                    # Jinja2 HTML templates (home, demo, past, about)
static/                       # CSS and images
```

## Data flow

**Scraper agent** (runs on a schedule, independent of Flask):
1. `scrape_uw_blog()` fetches the UW Alerts blog via BeautifulSoup
2. `query_recent_incidents()` fetches recent DB rows for duplicate detection
3. Claude (Haiku by default) decides if the scraped content is new; if so, calls `geocode_address()` then `upsert_alert()` which writes to `incidents` + `alerts` tables
4. `mark_no_update` terminates the loop when nothing new is found
5. `DRY_RUN=true` skips all DB writes for safe testing

**Flask app** (reads from Postgres; falls back to legacy CSV path for `/fully_update`):
1. Routes call `db.query_incidents_as_dataframe(hours=N)` for recent alerts
2. Result is passed to `get_folium_map()` + `attach_marker_ids()` in `visualization_manager`
3. Rendered map HTML is passed directly to Jinja2 templates via `map_html=`

**Key routes:**
- `/` — last 7 days of alerts (Postgres)
- `/demo` — last 24 h with custom text input (Postgres)
- `/past` — all historical alerts (Postgres)
- `/fully_update` — triggers live scrape using the legacy OpenAI parser, writes to CSV

## Database schema

Two tables: `incidents` (one row per physical event, holds geocoded location and category) and `alerts` (one row per blog post — original + updates — with a `text_hash` unique constraint for deduplication). `db.py` joins them and returns a DataFrame shaped to match the visualization manager's column expectations.

## Notes

- The `uw-alert-web/` directory is both a Python package and the Flask app root; use relative imports (`.visualization_manager...`) inside it.
- The scraper defaults to `claude-haiku-4-5-20251001`; override via `ANTHROPIC_HAIKU_MODEL`.
- `geometry` in the legacy CSV stores Python list literals; loaded with `converters={'geometry': ast.literal_eval}`. The Postgres path returns a plain `{"location": {"lat": ..., "lng": ...}}` dict to preserve the same shape.
