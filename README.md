# UW Alerts Dashboard

[![Coverage Status](https://coveralls.io/repos/github/uw-alerts-data-science/uw-alerts-dashboard/badge.svg?branch=main)](https://coveralls.io/github/uw-alerts-data-science/uw-alerts-dashboard?branch=main)

A public civic tool that surfaces University of Washington campus safety alerts on an interactive map, with historical analytics and external data overlays.

---

## Current State

- **Scraper** (`scraper/`) — Claude-powered agentic scraper polling `emergency.uw.edu` every 6 hours, writing normalized incident data to PostgreSQL. Runs as a Kubernetes CronJob in production.
- **API** (`app/`) — FastAPI backend reading from PostgreSQL, serving map-ready incidents and ad-hoc query routes.
- **Frontend** (`frontend/`) — Next.js + MapLibre GL live alert view, consuming the FastAPI backend.

---

## Architecture

```
emergency.uw.edu
      │
      ▼
scraper/ (Claude tool-use — Kubernetes CronJob, every 6 hours)
      │
      ▼
PostgreSQL
      │
      ▼
FastAPI (app/)
      │
      ▼
Live Alert View (frontend/ — Next.js + MapLibre GL)
  Active incidents on map
  Tooltips: type, time, address
```

## Local Dev Setup

### Prerequisites

- Package managers: Windows — [Chocolatey](https://chocolatey.org/install), Mac — [Homebrew](https://docs.brew.sh/Installation)
- GNU make — build automation tool (`choco install make` / `brew install make`)
- [uv](https://docs.astral.sh/uv/) package manager (`choco install uv` / `brew install uv`)
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) or [OrbStack](https://orbstack.dev/) (runs postgres + the FastAPI backend + the Next.js frontend)
- API keys: `ANTHROPIC_API_KEY`, `GOOGLE_MAPS_API_KEY`

### Quickstart

```bash
# 1. Clone and install
git clone https://github.com/uw-alerts-data-science/uw-alerts-dashboard.git
cd uw-alerts-dashboard
uv sync   # syncs Python dependencies (also installs poethepoet)

# 2. Configure environment
cp .env.example .env   # fill in ANTHROPIC_API_KEY, GOOGLE_MAPS_API_KEY

# 3. Start everything
make dev
# → Builds + starts postgres, api, frontend; applies schema; seeds the DB
#   from data/snapshot/; installs git hooks; then tails the API logs.
#   API at http://localhost:8000 (docs at /docs), frontend at http://localhost:3000.
```

### Make commands

`make` is the single entry point for local dev — it wraps `docker compose` and the underlying `poe` tasks so there's one interface to remember. Run `make help` for the full list (scraper CLI commands included).

| Command | What it does |
|---|---|
| `make up` | Build and start postgres + api + frontend (`docker compose up --build`) |
| `make setup` | Postgres up + schema applied + seed from `data/snapshot/` + git hooks installed (no frontend/api) |
| `make dev` | `make setup`, then tail the API container's logs |
| `make down` | Stop all containers (keeps the `postgres_data` volume) |
| `make scraper` | Run the scraper once against the compose stack (`--profile jobs`) |
| `make run` / `make dry-run` | Run the scraper agent locally via `.venv` (real / dry-run) |
| `make test` / `make test-scraper` / `make test-scraper-full` | Run test suites |
| `make lint` | Lint scraper code with ruff |
| `make audit` | Print a data quality audit report for the dev database |

**Networking gotcha:** inside the compose network, containers reach each other by *service name* — the `api` container connects to the DB at `postgres://...@postgres:5432/...`. Anything on your Mac (psql, a locally-run scraper) uses `localhost:5432` instead. `docker-compose.yml` sets the in-network `DATABASE_URL` for you.

**Hot reload vs. rebuilds:** `docker-compose.override.yml` is applied automatically by `docker compose up` (which `make up`/`make dev` call), bind-mounting `./app` and running `fastapi dev --reload`, so source edits reload instantly. Dependency changes (`pyproject.toml` / `uv.lock`) still need a rebuild — `make up`/`make dev` always pass `--build`, so this is handled for you. For a production-like run that ignores the override, use `docker compose -f docker-compose.yml up --build` directly.

Poe tasks (`uv run poe --help`) are the layer `make` wraps for container/DB management — `uv run poe db-dump` (export DB to `data/snapshot/` CSVs) and `uv run poe db-seed` (seed from those CSVs) are the two without a dedicated `make` target.

## Scraper Service

The `scraper/` directory contains a Claude-powered agent that polls `emergency.uw.edu` and maintains a normalized PostgreSQL database. It is designed to run as a Kubernetes CronJob every 6 hours; `make scraper` runs it once locally against the compose stack.

## Deployment

Production runs on a DigitalOcean Kubernetes cluster (`uw-alerts-v2`), all in namespace `uw-alerts`:

- `api` — Deployment running the FastAPI backend
- `frontend` — Deployment running the Next.js app
- `postgres` — StatefulSet, self-hosted, backed by a `do-block-storage` PersistentVolumeClaim
- `uw-alerts-scraper` — CronJob, runs the incremental scrape every 6 hours

**CI/CD:** `.github/workflows/push-{api,frontend,scraper}-image.yml` each build and push their image to the DigitalOcean Container Registry, then `kubectl apply -f k8s/app/` (picks up any manifest changes — probes, resources, replicas, schedule) followed by `kubectl set image` to roll out the tag that was just built. Each triggers on push to `main` (path-filtered to its own directory) or manually via `workflow_dispatch`.

**Postgres is fully decoupled from deploys.** Rolling out a new API/frontend/scraper image never touches the database, restarts it, or changes its data — the StatefulSet + PVC persist independently of every other workload. There is no automatic schema migration or reseed anywhere in CI/CD.

**Schema changes and full-history backfills are manual, on-demand actions only.** `k8s/jobs/` holds Jobs that no workflow ever applies or creates — a human has to run them explicitly:

```bash
# Apply/re-apply the schema (idempotent: CREATE TABLE IF NOT EXISTS, never drops data)
kubectl create -f k8s/jobs/apply-schema-job.yaml

# Full-history backfill (idempotent: dedupes on text_hash, never duplicates)
kubectl create -f k8s/jobs/backfill-job.yaml

kubectl get jobs -n uw-alerts
kubectl logs -f -l job-name -n uw-alerts   # or: kubectl logs -f job/<generated-name>
```

Nothing wipes or reseeds the database automatically. To wipe it or redo the backfill, someone has to trigger that themselves.

## Testing

```bash
uv run poe test          # app + scraper unit tests, with coverage
make test-scraper        # scraper unit tests (no DB needed)
make test-scraper-full   # all scraper tests including DB tests (requires `make setup` first)
uv run poe lint          # lint check
```

## Project Structure

```
app/
  main.py                            # FastAPI routes: /health, /query/incidents/*, /api/alerts
  tests/

frontend/                           # Next.js + MapLibre GL app
  src/app/                          # Pages
  src/components/
  src/lib/

scraper/
  agent.py                          # Entry point — delegates to live_discovery
  live_discovery.py                 # Page-walk discovery + per-article agent loop
  config.py                         # Env var validation
  prompts/                          # Jinja-templated system prompts
    system_prompt.j2
    batch_system_prompt.j2
    _article_block_parsing.j2       # Shared partial: article structure + field guide
  scripts/
    batch_history.py                # Parallel bulk importer (50 workers)
    audit.py                        # DB audit report
  tools/
    scrape.py                       # Fetch emergency.uw.edu
    database.py                     # query_recent_incidents, upsert_alert, known_source_urls, find_incident_id_by_source_url
    geocode.py                      # Google Maps geocoding
  db/
    schema.sql                      # PostgreSQL DDL
    schema.py / wait.py             # Schema application + Postgres readiness polling (used by `make setup`)
    models.py                       # Pydantic contract mirroring schema.sql
    migrate.py                      # CSV → PostgreSQL migration (one-time)

data/
  uw_alerts_clean.csv               # Legacy source data (historical migration provenance)
  snapshot/                         # CSV snapshot used to seed a fresh dev DB
  SeattleGISData/                   # U-District street network GeoJSON

docker-compose.yml / docker-compose.override.yml   # postgres + api + frontend (+ scraper, profile "jobs")
Dockerfile                          # Production API image
docker/scraper.Dockerfile           # Scraper image
k8s/
  app/                               # Applied by CI on every deploy (api, frontend, postgres, scraper CronJob, ingress)
  jobs/                              # NEVER applied by CI — manual-only (schema apply, full backfill)
  cluster/                           # Ingress-nginx / cert-manager cluster add-ons

docs/                               # Project planning and specs

.github/workflows/
  build_test.yml                    # CI: app tests + scraper tests (with Postgres) + docker build
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
