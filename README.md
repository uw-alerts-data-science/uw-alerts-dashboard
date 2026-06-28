# UW Alerts Dashboard

[![Coverage Status](https://coveralls.io/repos/github/evanyfyip/uw-alert-web/badge.svg?branch=main)](https://coveralls.io/github/evanyfyip/uw-alert-web?branch=main)

A public civic tool that surfaces University of Washington campus safety alerts on an interactive map, with historical analytics and external data overlays.

---

## Current State

The `main` branch reflects a working v1 implementation:

- **Scraper** (`scraper/`) — Claude-powered agentic scraper polling `emergency.uw.edu` every 15 min, writing normalized incident data to PostgreSQL. Production-ready and stable.
- **Flask app** (`uw-alert-web/`) — Folium map visualization, reading from PostgreSQL. Functional but being replaced.
- **Migration complete** — legacy CSV data (98 incidents, 265 alerts) migrated to PostgreSQL.

The Flask + Folium frontend is being retired in favor of a Next.js + MapLibre GL + FastAPI stack. The scraper service is stable and will not change significantly.

---

## Target Architecture

```
emergency.uw.edu
      │
      ▼
scraper/ (Claude tool-use — Kubernetes CronJob, every 15 min)
      │
      ▼
PostgreSQL
      │
      ▼
FastAPI
      │
      ├──────────────────────────────────────────────────────┐
      ▼                                                      ▼
Live Alert View (Next.js + MapLibre GL)        Analytics Dashboard (Next.js + Recharts)
  Active incidents on map                        Filterable historical map
  Tooltips: type, time, address                  Linked charts (time-series, category)
  15-min polling + last-updated timestamp        External data overlays (Census, Seattle Open Data)
```

---

## Roadmap

### Phase 1 — Thin Vertical Slice (target: end of July 2026)
- [ ] FastAPI rewrite — replace Flask with FastAPI, expose `/alerts/live` endpoint
- [ ] Next.js frontend — MapLibre GL map consuming FastAPI, live alert markers + tooltips
- [ ] Deploy to DigitalOcean Kubernetes at `uwalerts.live`

### Phase 2 — Analytics Dashboard (target: mid-August 2026)
- [ ] Historical filtering by date range, category, location
- [ ] Recharts dashboard: time-series, category breakdown, stat widgets
- [ ] External dataset integrations (DS-specced — see `docs/specs/`)

### Phase 3 — Stretch
- [ ] dbt transformation layer
- [ ] MCP server exposing incidents database as Claude tools
- [ ] Natural language query interface

---

## Project Structure

```
scraper/
  scraper_agent.py                  # Entry point — Claude tool-use loop
  batch_history.py                  # Parallel bulk importer (50 workers)
  system_prompt.py                  # Agent system prompt
  config.py                         # Env var validation
  tools/
    scrape.py                       # Fetch emergency.uw.edu
    database.py                     # query_recent_incidents, upsert_alert
    geocode.py                      # Google Maps geocoding
  db/
    schema.sql                      # PostgreSQL DDL
    migrate.py                      # CSV → PostgreSQL migration (one-time)

uw-alert-web/                       # v1 Flask app (being retired)
  uw-alert-web.py                   # Flask routes
  parse_uw_alerts/                  # Legacy scraper + GPT parser
  visualization_manager/            # Folium map generation

data/
  uw_alerts_clean.csv               # Legacy data (read-only after migration)
  SeattleGISData/                   # U-District street network GeoJSON

docs/                               # Project planning and specs

.github/workflows/
  build_test.yml                    # CI: Flask tests + scraper tests (with Postgres)
```

---

## Local Development

### Prerequisites

- Python 3.10–3.11
- [uv](https://docs.astral.sh/uv/) package manager
- Docker (for local PostgreSQL)
- API keys: `ANTHROPIC_API_KEY`, `GOOGLE_MAPS_API_KEY`

> **Windows users:** The `make` commands below require WSL or GNU Make. Use the `uv run` equivalents listed in each section instead — they work natively on Windows.

### Scraper

**Mac/Linux:**
```bash
make db-up          # start Postgres in Docker
make schema         # create tables and indexes
make dry-run        # run agent without writing to DB
make run            # run agent for real
make batch-history  # import full historical archive
make audit          # data quality report
make db-shell       # inspect the database
```

**Windows (uv run equivalents):**
```powershell
# Start Postgres in Docker
docker run -d --name uw-alerts-pg -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=uw_alerts_dev -p 5432:5432 postgres:15

# Apply schema
docker exec -i uw-alerts-pg psql -U postgres uw_alerts_dev < scraper/db/schema.sql

# Run agent (dry run — no DB writes)
$env:DATABASE_URL="postgres://postgres:postgres@localhost:5432/uw_alerts_dev"; $env:DRY_RUN="true"; uv run python -m scraper.scraper_agent

# Run agent for real
$env:DATABASE_URL="postgres://postgres:postgres@localhost:5432/uw_alerts_dev"; uv run python -m scraper.scraper_agent

# Import full historical archive
$env:DATABASE_URL="postgres://postgres:postgres@localhost:5432/uw_alerts_dev"; uv run python -m scraper.batch_history

# Data quality report
$env:DATABASE_URL="postgres://postgres:postgres@localhost:5432/uw_alerts_dev"; uv run python -m scraper.audit

# Inspect the database
docker exec -it uw-alerts-pg psql -U postgres uw_alerts_dev
```

### Flask app (v1 — being retired)

**Mac/Linux:**
```bash
uv sync
make serve        # foreground — http://127.0.0.1:5000
make serve-up     # background
make serve-down   # stop background server
```

**Windows:**
```powershell
uv sync
cd uw-alert-web
uv run flask --app=uw-alert-web run
# → http://127.0.0.1:5000
```

### Environment Variables

Copy `.env.example` (or create `.env`) in the repo root:

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API key |
| `GOOGLE_MAPS_API_KEY` | Geocoding |
| `DATABASE_URL` | `postgres://user:pass@host:5432/dbname` |
| `DRY_RUN` | Set to `true` to skip DB writes |

`python-dotenv` loads `.env` automatically when running via `uv run`. On Windows, you can also set variables in PowerShell with `$env:VAR="value"` before each command (as shown above), or use a tool like [direnv](https://direnv.net/).

### Testing

**Mac/Linux:**
```bash
uv run poe test           # Flask app tests
make test-scraper         # Scraper unit tests (no DB required)
make test-scraper-full    # All scraper tests (requires make schema)
uv run poe lint           # Lint
```

**Windows:**
```powershell
uv run poe test                                                                    # Flask app tests
uv run pytest scraper/tests/ --ignore=scraper/tests/test_schema.py --ignore=scraper/tests/test_migrate.py -v  # Scraper unit tests
uv run poe lint                                                                    # Lint
```

---

## Git Workflow

### Branches

Branch names follow the `<type>/<short-description>` pattern:

```
feat/live-alerts-endpoint
fix/tooltip-overflow
chore/update-dependencies
docs/add-api-spec
refactor/scraper-retry-logic
test/geocode-edge-cases
ci/add-scraper-job
```

`main` is always deployable. Work happens on feature branches and merges via PR.

### Conventional Commits

All commits follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<optional scope>): <short description>

[optional body]
```

| Type | When to use |
|---|---|
| `feat` | New feature or capability |
| `fix` | Bug fix |
| `chore` | Maintenance, dependencies, tooling |
| `docs` | Documentation only |
| `refactor` | Code change with no behavior change |
| `test` | Adding or updating tests |
| `perf` | Performance improvement |
| `ci` | CI/CD pipeline changes |

**Examples:**

```
feat(scraper): add 429 retry with exponential backoff
fix(map): tooltip overflow on mobile viewports
chore(deps): bump anthropic sdk to 0.40.0
docs: add git workflow to README
test(geocode): add null address edge case
refactor(database): extract upsert logic into helper
```

### Worktrees

Use git worktrees to work on multiple branches simultaneously without stashing or context switching:

```bash
# Create a worktree for a new feature (branch must already exist)
git worktree add .worktrees/feat-my-feature feat/my-feature

# Create the branch and worktree together
git worktree add .worktrees/feat-my-feature -b feat/my-feature

# List active worktrees
git worktree list

# Remove a worktree when done (after merging)
git worktree remove .worktrees/feat-my-feature
```

Worktrees live in `.worktrees/` (gitignored). Each is a full working directory on its own branch.

**Convention:** worktree directory name matches the branch name with `/` replaced by `-`:
```
branch:   feat/live-alerts-endpoint
worktree: .worktrees/feat-live-alerts-endpoint
```

---

## API Keys

- [Anthropic (Claude)](https://console.anthropic.com/)
- [Google Maps](https://developers.google.com/maps/documentation/javascript/get-api-key)
