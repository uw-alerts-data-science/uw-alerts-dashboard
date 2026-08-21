# Single entry point for local dev: full-stack container orchestration
# (postgres + api + frontend, via docker compose) and scraper operations.
# Container/DB commands here wrap the underlying `poe`/`docker compose`
# calls (see `uv run poe --help`) so there's one interface to remember.
DB_TEST     = uw_alerts_test
DB_USER     = postgres
DB_PASSWORD = postgres
DB_PORT     = 5432
TEST_DB_URL = postgres://$(DB_USER):$(DB_PASSWORD)@localhost:$(DB_PORT)/$(DB_TEST)

.PHONY: up down setup dev scraper run dry-run batch-history batch-history-dry seed audit test test-scraper test-scraper-full lint help

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

up: ## Build and start postgres + api + frontend (docker compose up --build)
	docker compose up --build

down: ## Stop all containers (keeps the postgres_data volume)
	uv run poe db-down

setup: ## Start postgres, apply schema, seed DB, install git hooks (no frontend/api)
	uv run poe setup

dev: ## Full local dev: setup, then tail the API container logs
	uv run poe dev

scraper: ## Run the scraper once against the compose stack (profile: jobs)
	docker compose --profile jobs run --rm scraper

run: ## Run the scraper agent once (requires .env or exported env vars)
	set -a && . ./.env && set +a && .venv/bin/python -m scraper.agent

dry-run: ## Run the scraper agent in dry-run mode (no DB writes)
	set -a && . ./.env && DRY_RUN=true .venv/bin/python -m scraper.agent

test: ## Run app + scraper unit tests
	uv run poe test

test-scraper: ## Run scraper unit tests (no DB required)
	.venv/bin/pytest scraper/tests/ --ignore=scraper/tests/test_schema.py --ignore=scraper/tests/test_migrate.py --ignore=scraper/tests/test_schema_apply.py -v

test-scraper-full: ## Run all scraper tests including DB tests (requires poe setup first)
	TEST_DATABASE_URL=$(TEST_DB_URL) .venv/bin/pytest scraper/tests/ -v

batch-history: ## Scrape all 19 blog pages oldest-first and write to DB (idempotent)
	set -a && . ./.env && set +a && .venv/bin/python -m scraper.scripts.batch_history

batch-history-dry: ## Dry run of full history scrape — logs what would be written, no DB writes
	set -a && . ./.env && DRY_RUN=true .venv/bin/python -m scraper.scripts.batch_history

seed: ## Seed an empty DB with full history (skips if incidents table already populated)
	set -a && . ./.env && set +a && \
	  COUNT=$$(.venv/bin/python -c "import psycopg2,os; c=psycopg2.connect(os.environ['DATABASE_URL']); cur=c.cursor(); cur.execute('SELECT COUNT(*) FROM incidents'); print(cur.fetchone()[0])"); \
	  if [ "$$COUNT" = "0" ]; then \
	    echo "Database is empty — running full history import..."; \
	    .venv/bin/python -m scraper.scripts.batch_history; \
	  else \
	    echo "Database already contains $$COUNT incident(s). Run 'make batch-history' to force re-import."; \
	  fi

audit: ## Print a data quality audit report for the dev database
	set -a && . ./.env && set +a && .venv/bin/python -m scraper.scripts.audit

lint: ## Lint scraper code with ruff
	.venv/bin/ruff check scraper/
