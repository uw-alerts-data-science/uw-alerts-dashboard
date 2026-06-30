# Local Dev Setup — Design Spec
_2026-06-29_

## Goal

Give contributors a single cross-platform command (`uv run poe dev`) that boots postgres, applies the schema, seeds from the snapshot, and starts the Flask app. Works on Mac and Windows via `uv`/`poe` + Docker Compose.

## New Files

### `docker-compose.yml` (root)
Defines the `postgres:15` dev service. Named volume for persistence. Port `5432` exposed to localhost. Env vars match the default `DATABASE_URL` in `.env.example`.

```yaml
services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: uw_alerts_dev
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

### `scraper/db/wait.py`
`wait_for_postgres(timeout=30, interval=1)` — retries a psycopg2 connection once per second. Prints a ready message on success, raises `TimeoutError` if postgres doesn't respond within `timeout` seconds.

### `scraper/db/schema.py`
`apply_schema()` — reads `scraper/db/schema.sql` and executes it via psycopg2. Idempotent: the SQL uses `CREATE TABLE IF NOT EXISTS` so re-runs are safe.

## New Poe Tasks (`pyproject.toml`)

| Task | What it does |
|---|---|
| `poe serve` | Starts Flask (`flask --app=uw-alert-web run`) from the `uw-alert-web` dir |
| `poe setup` | `docker compose up -d` → wait → apply schema → `db-seed` |
| `poe dev` | `setup` then `serve` (full environment, blocks on Flask) |
| `poe db-down` | `docker compose down` |

`poe setup` uses a poe `sequence` with `script` steps calling `scraper.db.wait:wait_for_postgres` and `scraper.db.schema:apply_schema`. No shell syntax — fully cross-platform.

## README Update

Replace the two separate quickstarts (Flask-only and Scraper) with a unified **Local Dev Setup** section:

1. Clone + `uv sync`
2. `cp .env.example .env` — fill in `ANTHROPIC_API_KEY`, `GOOGLE_MAPS_API_KEY`, `MAPBOX_API_KEY`
3. `uv run poe dev` — boots postgres, seeds DB, starts Flask at http://127.0.0.1:5000

Keep the existing Makefile docs for the scraper (advanced use) but note `poe` as the recommended contributor path.

## Constraints

- No shell syntax in poe tasks (breaks Windows cmd/PowerShell)
- All Python helpers invoked via `poe script` type, not inline `-c` strings
- `poe setup` must be idempotent (safe to re-run on an already-running stack)
- Branch: `feat/postgres-db-dump`
