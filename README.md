# UW Alerts Dashboard

[![Coverage Status](https://coveralls.io/repos/github/evanyfyip/uw-alert-web/badge.svg?branch=main)](https://coveralls.io/github/evanyfyip/uw-alert-web?branch=main)

## Overview

A Flask web application that visualizes University of Washington campus safety alerts on an interactive map. It scrapes the UW Alerts blog, parses incidents using Claude AI, geocodes addresses via Google Maps, and renders a Folium map with heatmap overlays. The repository also includes a production-ready agentic scraper service that polls `emergency.uw.edu` on a schedule and writes normalized incident data to PostgreSQL.

## Architecture

```
UW Alerts Blog (emergency.uw.edu)
        │
        ▼
  scraper/ (Claude agent — runs every 15 min)
  ├── scrape_uw_blog()       fetch latest alert
  ├── query_recent_incidents() check for duplicates
  ├── geocode_address()      Google Maps → lat/lng
  └── upsert_alert()         write to PostgreSQL
        │
        ▼
   PostgreSQL
   ├── incidents table
   └── alerts table
        │
        ▼
  uw-alert-web/ (Flask app)
  ├── parse_uw_alerts.py     (legacy CSV path)
  └── visualization_manager/ → Folium map → browser
```

## Local Dev Setup

### Prerequisites
For this project the key installations are to have uv, Docker, Chocolatey/Homebrew, 
- Package Managers: Windows - [Download Chocolatey](https://chocolatey.org/install), Mac - [Download Brew Package Manager](https://docs.brew.sh/Installation)
- GNU make - Build automation tool
- [uv](https://docs.astral.sh/uv/) package manager
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for local PostgreSQL)
- API keys: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_MAPS_API_KEY`, `MAPBOX_API_KEY`

### Quickstart

```bash
# Prerequisites
# 1 Install your package manager `choco` for windows or `brew` for mac
# See documentation above

# 2. Install uv and make with package manager
# Windows
choco install uv
choco install make

# Mac
brew install uv
brew install make

# Repository setup
# 1. Clone and install
git clone https://github.com/uw-alerts-data-science/uw-alerts-dashboard.git
cd uw-alerts-dashboard
uv sync # Sync python dependencies (this will also install poethepoet)

# 2. Configure environment
# IMPORTANT: You must get actual API keys and replace these templates
cp .env.example .env   # fill in OPENAI_API_KEY, ANTHROPIC_API_KEY, GOOGLE_MAPS_API_KEY, MAPBOX_API_KEY

# 3. Start everything
uv run poe dev
# → Boots postgres, applies schema, seeds DB, starts Flask (the webapp) at http://127.0.0.1:5000
```

### Poe tasks
Poethepoet is a task runner that provides a simple way to define project tasks. We will use a combination
of uv (package manager) and poe to setup the backend python services (currently flask app, postgres database etc).

| Command | What it does |
|---|---|
| `uv run poe dev` | Full environment: postgres + seed + Flask (blocks) |
| `uv run poe setup` | Postgres up + schema + seed (no Flask) |
| `uv run poe serve` | Flask only (requires postgres already running) |
| `uv run poe db-down` | Stop postgres container |
| `uv run poe db-dump` | Export DB to `data/snapshot/` CSVs |
| `uv run poe db-seed` | Seed DB from `data/snapshot/` CSVs |
| `uv run poe test` | Flask app unit tests |
| `uv run poe test-scraper` | Scraper unit tests (no DB required) |
| `uv run poe lint` | Lint check |

## Scraper Service

The `scraper/` directory contains a Claude-powered agent that polls `emergency.uw.edu` and maintains a normalized PostgreSQL database. It is designed to run as a Kubernetes CronJob every 15 minutes.

### Makefile commands
Once we migrate to using a different frontend stack, it may make sense to utilize `make` to orchestrate both
the frontend and backend with a single interface. Recommended setup (Windows [chocolatey & make setup](https://medium.com/@AliMasaoodi/installing-make-on-windows-10-using-chocolatey-a-step-by-step-guide-5e178c449394))

```bash
make db-up      # start Postgres container
make schema     # create tables and indexes
make dry-run    # run agent in dry-run mode (no writes)
make run        # run agent for real (needs ANTHROPIC_API_KEY etc.)
make db-shell   # inspect the database
```

## Testing

```bash
uv run poe test          # Flask app tests (42 tests)
make test-scraper        # Scraper unit tests (20 tests, no DB needed)
make test-scraper-full   # All scraper tests including DB (requires make schema)
uv run poe lint          # Lint check
```

## Project Structure

```
uw-alert-web/
  uw-alert-web.py                   # Flask routes
  parse_uw_alerts/                  # Legacy scraper + GPT parser
  visualization_manager/            # Folium map generation

scraper/
  scraper_agent.py                  # Entry point — Claude tool-use loop
  system_prompt.py                  # Agent system prompt
  config.py                         # Env var validation
  logging_config.py                 # JSON structured logging
  tools/
    scrape.py                       # Fetch emergency.uw.edu
    database.py                     # query_recent_incidents, upsert_alert
    geocode.py                      # Google Maps geocoding
  db/
    schema.sql                      # PostgreSQL DDL
    migrate.py                      # CSV → PostgreSQL migration

data/
  uw_alerts_clean.csv               # Legacy data store (read-only after migration)

.github/workflows/
  build_test.yml                    # CI: Flask tests + scraper tests (with Postgres)
```

## API Keys

- [Anthropic (Claude)](https://console.anthropic.com/)
- [Google Maps](https://developers.google.com/maps/documentation/javascript/get-api-key)
- [Mapbox](https://docs.mapbox.com/help/getting-started/access-tokens/)
