# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Flask web application that visualizes University of Washington campus safety alerts on an interactive map. It scrapes the UW Alerts blog, parses incidents using OpenAI GPT, geocodes addresses via Google Maps, and renders them as a Folium map with heatmap overlays.

## Environment Setup

```bash
uv sync       # installs all dependencies including dev tools
```

Requires a `.env` file in the root directory with:
```
OPENAI_API_KEY='...'
GOOGLE_MAPS_API_KEY='...'
MAPBOX_API_KEY='...'
```

## Running the App

```bash
cd uw-alert-web
uv run flask --app=uw-alert-web run
```

App runs at http://127.0.0.1:5000

## Tests & Linting

```bash
uv run poe test      # run all tests with coverage report
uv run poe fmt       # format + auto-fix lint issues (ruff format + ruff check --fix)
uv run poe lint      # check lint without modifying files

# Run a single test file
cd uw-alert-web && uv run python -m unittest tests/test_parse_uw_alerts.py
```

CI runs on Python 3.10 and 3.11 using uv. Ruff config is in `pyproject.toml` under `[tool.ruff]`. Disabled: `E501` (line length).

## Architecture

```
uw-alert-web/
  uw-alert-web.py             # Flask app — routes only, no business logic
  parse_uw_alerts/
    parse_uw_alerts.py        # GPT-based parser + UW blog scraper + geocoding
  visualization_manager/
    visualization_manager.py  # Folium map generation, marker attachment, heatmap
    process_seattle_streets.py # GeoDataFrame processing for Seattle street data
  tests/                      # unittest-based tests for parse and viz modules

data/
  uw_alerts_clean.csv         # Primary data store — read and written at runtime
  SeattleGISData/             # Seattle street GIS shapefiles for map context

templates/                    # Jinja2 HTML templates (home, demo, past, about)
static/                       # CSS and images
```

**Data flow:**
1. `parse_uw_alerts.scrape_uw_alerts()` fetches the UW Alerts blog (BeautifulSoup)
2. `prompt_gpt()` sends alert text to OpenAI to extract structured fields (date, time, address, category, summary)
3. `clean_gpt_output()` geocodes the address via Google Maps API → lat/lng
4. Result is appended to `data/uw_alerts_clean.csv`
5. Flask routes load the CSV, call `get_urgent_incidents()` to filter by time window, then `get_folium_map()` + `attach_marker_ids()` to render the map HTML
6. The rendered map HTML string is passed directly to Jinja2 templates via `map_html=`

**Key pages:**
- `/` — home page, alerts from the last 7 days
- `/demo` — demo page with text input to add custom alerts (last 24h)
- `/past` — all historical alerts
- `/fully_update` — triggers live scrape of UW Alerts blog

## Notes

- The `uw-alert-web/` directory is both a Python package and the Flask app root — imports use relative syntax (`.visualization_manager...`)
- `data/uw_alerts_clean.csv` is mutated by the `/update_map` and `/fully_update` routes at runtime
- The `geometry` column in the CSV stores Python list literals; it's loaded with `converters={'geometry': ast.literal_eval}`
