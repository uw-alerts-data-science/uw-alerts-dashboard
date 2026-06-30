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
