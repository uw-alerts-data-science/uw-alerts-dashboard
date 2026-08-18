# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A civic tool that visualizes University of Washington campus safety alerts on an interactive map. A Claude-based agentic scraper fetches alerts, geocodes them via Google Maps, and stores them to PostgreSQL. A FastAPI backend (`app/`) queries Postgres and serves JSON to a Next.js + MapLibre GL frontend (`frontend/`).

## Environment Setup

```bash
uv sync       # installs all Python dependencies (app + scraper) including dev tools
```

Requires a `.env` file in the root directory. Copy `.env.example` and fill in your values:
```
# API (app/)
GOOGLE_MAPS_API_KEY='...'
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

Full-stack local dev goes through `make` (wraps `docker compose` and `poe` under the hood — see `make help` for the complete list):

```bash
make up         # Build and start postgres + api + frontend (docker compose up --build)
make setup      # Postgres up + schema applied + seed from data/snapshot/ + git hooks installed
make dev        # setup, then tail the API container's logs
make down       # Stop all containers (keeps the postgres_data volume)
make scraper    # Run the scraper once against the compose stack (profile: jobs)
```

```bash
# Tests
uv run poe test           # app + scraper tests with coverage
uv run poe test-scraper   # scraper-only tests (no DB required)
make test-scraper-full    # all scraper tests including DB tests (requires `make setup` first)

# Single test file
uv run python -m pytest app/tests/test_main.py -v
pytest scraper/tests/test_agent.py -v

# Lint / format
uv run poe fmt            # ruff format + ruff check --fix
uv run poe lint           # check only, no writes

# Scraper (dry run — no DB writes)
DRY_RUN=true python -m scraper.agent
make dry-run               # same, via the Makefile (sources .env first)

# CSV → Postgres migration (one-time)
python -m scraper.db.migrate
```

CI runs on Python 3.12 using uv, matching the production Docker image. Ruff config is in `pyproject.toml` (`[tool.ruff]`); `E501`, `W291`, `W293` are disabled.

## Architecture

```
app/                           # FastAPI backend (serves the frontend + ad-hoc query routes)
  main.py                       # Routes: /health, /query/incidents/recent, /query/incidents/search, /api/alerts
  tests/

frontend/                      # Next.js + MapLibre GL app
  src/app/                      # Pages (incl. src/app/recent/)
  src/components/
  src/lib/

scraper/                      # Agentic scraper (runs independently of app/)
  agent.py                     # Thin entry point — delegates to live_discovery.run_live_discovery()
  live_discovery.py            # Live incremental scrape: page-walk discovery + per-article agent loop
  config.py                   # Env loading; Anthropic client factory (direct or Azure)
  prompts/                    # Jinja-templated system prompts (rendered via render_prompt())
    system_prompt.j2
    batch_system_prompt.j2
    _article_block_parsing.j2  # Shared partial: article structure + field extraction guide
  scripts/
    batch_history.py           # Parallel bulk importer (historical backfill)
    audit.py                   # DB audit report (record counts, category distribution, data quality)
  tools/
    scrape.py                 # BeautifulSoup fetch of UW Alerts blog (scrape_page, scrape_article_urls, scrape_article)
    geocode.py                # Google Maps geocoding
    database.py                # query_recent_incidents, upsert_alert, known_source_urls, find_incident_id_by_source_url (Postgres)
  db/
    models.py                  # Pydantic contract mirroring schema.sql (IncidentCategory, AlertType, etc.)
    schema.py / wait.py        # Schema application + Postgres readiness polling (used by `make setup`)
    migrate.py                # One-time CSV → Postgres migration
  tests/                      # pytest-based tests for all scraper modules

data/
  uw_alerts_clean.csv         # Legacy source data (retained for historical migration provenance)
  snapshot/                   # CSV snapshot used to seed a fresh dev DB (`make setup` / `poe db-seed`)
  SeattleGISData/             # Seattle street GIS shapefiles

docker-compose.yml / docker-compose.override.yml   # postgres + api + frontend (+ scraper, profile "jobs")
Dockerfile                    # Production API image (built from app/ + pyproject.toml/uv.lock)
docker/scraper.Dockerfile     # Scraper image
k8s/app/                       # Applied by CI on every deploy: api, frontend, postgres, scraper CronJob, ingress
k8s/jobs/                      # NEVER applied by CI — manual-only Jobs (schema apply, full backfill)
```

## Data flow

**Scraper agent** (runs on a schedule, independent of the API):
1. `_discover_urls_to_process()` walks blog listing pages newest-first via `scrape_article_urls()`, expanding only while every URL on a page is unseen (checked deterministically via `known_source_urls()`); stops expanding once a page has a known URL, capped at `max_pages` with a warning logged if the cap is hit while still all-new.
2. For every article URL in that range, `_process_live_article()` looks up `find_incident_id_by_source_url()` — a plain SQL fact, not an LLM judgment call — and tells Claude upfront whether this is a brand-new incident or an update to a known one.
3. Claude parses the article into blocks and calls `geocode_address()`/`upsert_alert()` per block, looping until `end_turn` (not stopping after the first write) — so a multi-block article or a burst of several new incidents in one poll are all captured, not just the first one.
4. `upsert_alert()` on an update also refines the incident's own `category`/address/`lat`/`lng`/`occurred_at` via COALESCE when the alert text is a genuine correction (vs. narrative color) — guided by few-shot examples in `system_prompt.j2`.
5. Zero new alerts for an article is a normal outcome, not an error — most articles on a given cycle will already be fully recorded.
6. `DRY_RUN=true` skips all DB writes for safe testing.

**FastAPI backend** (`app/main.py`, reads from Postgres):
1. `/api/alerts` — map-ready incidents (optionally filtered to alerts scraped in the last `hours`), consumed by the Next.js frontend.
2. `/query/incidents/recent` / `/query/incidents/search` — ad-hoc query helpers over `scraper.tools.database`.
3. `/health` — verifies DB connectivity.

**Frontend** (`frontend/`, Next.js + MapLibre GL): fetches from the FastAPI backend and renders incidents on an interactive map.

## Database schema

Two tables: `incidents` (one row per physical event, holds geocoded location and category) and `alerts` (one row per blog post — original + updates — with a `text_hash` unique constraint for deduplication). `app/main.py` and `scraper/tools/database.py` both query these directly via `psycopg2`.

## Deployment

Production: DigitalOcean Kubernetes cluster `uw-alerts-v2`, namespace `uw-alerts`. `.github/workflows/push-{api,frontend,scraper}-image.yml` build+push each image on push to `main` (path-filtered) or `workflow_dispatch`, then `kubectl apply -f k8s/app/` + `kubectl set image` roll out the new tag.

Postgres (`postgres` StatefulSet + PVC, `k8s/app/postgres.yaml`) is fully decoupled from all three deploy workflows — an image rollout never touches it. **Schema apply and full-history backfill are manual-only**: `k8s/jobs/apply-schema-job.yaml` and `k8s/jobs/backfill-job.yaml` are never applied by CI; a human runs `kubectl create -f <file>` deliberately. There is no automatic wipe or reseed anywhere — see the README's Deployment section for the exact commands.

## Notes

- The scraper defaults to `claude-haiku-4-5-20251001`; override via `ANTHROPIC_HAIKU_MODEL`.
- Local Postgres runs in Docker (`postgres:15`) via `docker-compose.yml`; inside the compose network, containers reach it at `postgres:5432`, while host tools (psql, a locally-run scraper) use `localhost:5432`.
