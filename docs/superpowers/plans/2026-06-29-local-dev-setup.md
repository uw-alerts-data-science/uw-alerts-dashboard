# Local Dev Setup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give contributors a single cross-platform command (`uv run poe dev`) that boots postgres, applies the schema, seeds from the snapshot, and starts the Flask app.

**Architecture:** A `docker-compose.yml` defines the postgres service. Two new Python helpers (`wait.py`, `schema.py`) handle readiness polling and schema application via psycopg2 — no shell syntax, so they work on Mac and Windows. Four new poe tasks (`serve`, `setup`, `dev`, `db-down`) wire everything together.

**Tech Stack:** Python 3.10+, psycopg2-binary, poethepoet, Docker Compose v2, Flask

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `docker-compose.yml` | postgres:15 service + named volume |
| Create | `scraper/db/wait.py` | `wait_for_postgres()` — retries psycopg2 until ready |
| Create | `scraper/db/schema.py` | `apply_schema()` — reads schema.sql, executes via psycopg2 |
| Create | `scraper/tests/test_wait.py` | Unit tests for wait_for_postgres (mocked psycopg2) |
| Create | `scraper/tests/test_schema_apply.py` | Integration test for apply_schema (real test DB) |
| Modify | `pyproject.toml` | Add `serve`, `setup`, `dev`, `db-down` poe tasks |
| Modify | `README.md` | Unified "Local Dev Setup" quickstart section |

---

### Task 1: `scraper/db/wait.py` — postgres readiness helper

**Files:**
- Create: `scraper/db/wait.py`
- Create: `scraper/tests/test_wait.py`

- [ ] **Step 1: Write the failing tests**

Create `scraper/tests/test_wait.py`:

```python
import psycopg2
import pytest
from unittest.mock import MagicMock, call, patch


def test_wait_succeeds_immediately():
    with patch("scraper.db.wait.psycopg2.connect") as mock_connect:
        mock_connect.return_value = MagicMock()
        from scraper.db.wait import wait_for_postgres
        wait_for_postgres(url="postgres://localhost/test", interval=0)
        mock_connect.assert_called_once_with("postgres://localhost/test")


def test_wait_retries_then_succeeds():
    with patch("scraper.db.wait.psycopg2.connect") as mock_connect:
        mock_connect.side_effect = [
            psycopg2.OperationalError(),
            psycopg2.OperationalError(),
            MagicMock(),
        ]
        from scraper.db.wait import wait_for_postgres
        wait_for_postgres(url="postgres://localhost/test", interval=0)
        assert mock_connect.call_count == 3


def test_wait_raises_timeout():
    with patch("scraper.db.wait.psycopg2.connect") as mock_connect:
        mock_connect.side_effect = psycopg2.OperationalError()
        from scraper.db.wait import wait_for_postgres
        with pytest.raises(TimeoutError, match="not ready after"):
            wait_for_postgres(url="postgres://localhost/test", timeout=0.05, interval=0)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest scraper/tests/test_wait.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — `scraper.db.wait` doesn't exist yet.

- [ ] **Step 3: Implement `scraper/db/wait.py`**

```python
import os
import time

import psycopg2


def wait_for_postgres(url=None, timeout=30, interval=1):
    url = url or os.environ["DATABASE_URL"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            conn = psycopg2.connect(url)
            conn.close()
            print("Postgres is ready.")
            return
        except psycopg2.OperationalError:
            time.sleep(interval)
    raise TimeoutError(f"Postgres not ready after {timeout}s — is Docker running?")
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest scraper/tests/test_wait.py -v
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add scraper/db/wait.py scraper/tests/test_wait.py
git commit -m "feat(db): add wait_for_postgres helper"
```

---

### Task 2: `scraper/db/schema.py` — schema application helper

**Files:**
- Create: `scraper/db/schema.py`
- Create: `scraper/tests/test_schema_apply.py`

- [ ] **Step 1: Write the failing integration test**

Create `scraper/tests/test_schema_apply.py`:

```python
import os

import psycopg2
import pytest


@pytest.fixture(scope="module")
def test_db():
    url = os.environ.get("TEST_DATABASE_URL", "postgres://localhost/uw_alerts_test")
    sep = "&" if "?" in url else "?"
    try:
        conn = psycopg2.connect(url + sep + "connect_timeout=3")
    except psycopg2.OperationalError as e:
        pytest.skip(f"test DB unavailable: {e}")
    # Start with a clean slate
    with conn:
        with conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS alerts CASCADE")
            cur.execute("DROP TABLE IF EXISTS incidents CASCADE")
    yield conn
    conn.close()


def test_apply_schema_creates_tables(test_db):
    from scraper.db.schema import apply_schema
    apply_schema(url=os.environ.get("TEST_DATABASE_URL", "postgres://localhost/uw_alerts_test"))
    with test_db.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_name IN ('incidents', 'alerts') ORDER BY table_name"
        )
        tables = [row[0] for row in cur.fetchall()]
    assert tables == ["alerts", "incidents"]


def test_apply_schema_is_idempotent(test_db):
    from scraper.db.schema import apply_schema
    url = os.environ.get("TEST_DATABASE_URL", "postgres://localhost/uw_alerts_test")
    # Second call must not raise
    apply_schema(url=url)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
TEST_DATABASE_URL=postgres://postgres:postgres@localhost:5432/uw_alerts_test \
  uv run pytest scraper/tests/test_schema_apply.py -v
```

Expected: `ImportError` — `scraper.db.schema` doesn't exist yet. (Skip if no test DB available — that's fine for now; this is an integration test.)

- [ ] **Step 3: Implement `scraper/db/schema.py`**

```python
import os
from pathlib import Path

import psycopg2


def apply_schema(url=None):
    url = url or os.environ["DATABASE_URL"]
    sql = (Path(__file__).parent / "schema.sql").read_text()
    conn = psycopg2.connect(url)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(sql)
        print("Schema applied.")
    finally:
        conn.close()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
TEST_DATABASE_URL=postgres://postgres:postgres@localhost:5432/uw_alerts_test \
  uv run pytest scraper/tests/test_schema_apply.py -v
```

Expected: 2 tests pass (or skip if no test DB — both are acceptable at this stage).

- [ ] **Step 5: Commit**

```bash
git add scraper/db/schema.py scraper/tests/test_schema_apply.py
git commit -m "feat(db): add apply_schema helper"
```

---

### Task 3: `docker-compose.yml` — postgres service definition

**Files:**
- Create: `docker-compose.yml`

No unit tests — verified manually in Task 4.

- [ ] **Step 1: Create `docker-compose.yml` at the repo root**

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

- [ ] **Step 2: Verify it starts cleanly**

```bash
docker compose up -d
docker compose ps
```

Expected: `postgres` service shows `running` (healthy).

- [ ] **Step 3: Stop it**

```bash
docker compose down
```

- [ ] **Step 4: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add docker-compose.yml for local postgres"
```

---

### Task 4: Poe tasks — `serve`, `setup`, `dev`, `db-down`

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add the four new tasks to `pyproject.toml`**

Add after the existing `[tool.poe.tasks.db-seed]` block:

```toml
[tool.poe.tasks.serve]
help = "Start the Flask web app"
cmd = "uv run flask --app=uw-alert-web run"
cwd = "uw-alert-web"

[tool.poe.tasks.db-down]
help = "Stop local Postgres container"
cmd = "docker compose down"

[tool.poe.tasks.setup]
help = "Spin up postgres, apply schema, and seed from snapshot"
sequence = [
  { cmd = "docker compose up -d" },
  { script = "scraper.db.wait:wait_for_postgres" },
  { script = "scraper.db.schema:apply_schema" },
  { ref = "db-seed" },
]

[tool.poe.tasks.dev]
help = "Full local dev: postgres up, schema, seed, and Flask at http://127.0.0.1:5000"
sequence = [
  { ref = "setup" },
  { ref = "serve" },
]
```

- [ ] **Step 2: Verify `poe serve` starts Flask**

```bash
uv run poe serve
```

Expected: Flask starts at `http://127.0.0.1:5000`. Press Ctrl+C to stop.

- [ ] **Step 3: Verify `poe setup` runs end-to-end**

```bash
uv run poe setup
```

Expected output (in order):
```
Postgres is ready.
Schema applied.
Poe => python -c ...   # db-seed step
{'incidents_seeded': ..., 'alerts_seeded': ...}
```

- [ ] **Step 4: Verify `poe db-down` stops postgres**

```bash
uv run poe db-down
docker ps
```

Expected: no `uw-alerts` postgres container running.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "feat: add serve, setup, dev, db-down poe tasks"
```

---

### Task 5: README update

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace the two separate quickstarts with a unified "Local Dev Setup" section**

Replace the existing `## Quickstart — Flask App` section with the following. Keep everything after `## Scraper Service` unchanged (it documents the advanced/scraper-specific workflow via Makefile).

```markdown
## Local Dev Setup

### Prerequisites

- Python 3.10–3.11
- [uv](https://docs.astral.sh/uv/) package manager
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (for local PostgreSQL)
- API keys: `ANTHROPIC_API_KEY`, `GOOGLE_MAPS_API_KEY`, `MAPBOX_API_KEY`

### Quickstart

```bash
# 1. Clone and install
git clone https://github.com/uw-alerts-data-science/uw-alerts-dashboard.git
cd uw-alerts-dashboard
uv sync

# 2. Configure environment
cp .env.example .env   # fill in ANTHROPIC_API_KEY, GOOGLE_MAPS_API_KEY, MAPBOX_API_KEY

# 3. Start everything
uv run poe dev
# → Boots postgres, applies schema, seeds DB, starts Flask at http://127.0.0.1:5000
```

### Poe tasks

| Command | What it does |
|---|---|
| `uv run poe dev` | Full environment: postgres + seed + Flask (blocks) |
| `uv run poe setup` | Postgres up + schema + seed (no Flask) |
| `uv run poe serve` | Flask only (requires postgres already running) |
| `uv run poe db-down` | Stop postgres container |
| `uv run poe db-dump` | Export DB to `data/snapshot/` CSVs |
| `uv run poe db-seed` | Seed DB from `data/snapshot/` CSVs |
| `uv run poe test` | Flask app unit tests |
| `uv run poe lint` | Lint check |
```

- [ ] **Step 2: Verify the README renders correctly**

```bash
# Quick sanity check — no broken markdown headers
grep "^#" README.md
```

Expected: clean header hierarchy with no duplicate `## Quickstart` entries.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: unify local dev setup in README with poe quickstart"
```
