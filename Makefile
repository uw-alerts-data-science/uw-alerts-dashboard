# Local dev database (Docker)
DB_NAME     = uw_alerts_dev
DB_TEST     = uw_alerts_test
DB_USER     = postgres
DB_PASSWORD = postgres
DB_PORT     = 5432
DB_URL      = postgres://$(DB_USER):$(DB_PASSWORD)@localhost:$(DB_PORT)/$(DB_NAME)
TEST_DB_URL = postgres://$(DB_USER):$(DB_PASSWORD)@localhost:$(DB_PORT)/$(DB_TEST)

.PHONY: db-up db-down db-shell schema migrate run dry-run batch-history batch-history-dry seed audit test test-scraper test-scraper-full lint serve help

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

db-up: ## Start local Postgres in Docker
	docker run -d --name uw-alerts-pg \
		-e POSTGRES_PASSWORD=$(DB_PASSWORD) \
		-e POSTGRES_DB=$(DB_NAME) \
		-p $(DB_PORT):5432 \
		postgres:15
	@echo "Postgres running at localhost:$(DB_PORT). Run 'make schema' to initialize."

db-down: ## Stop and remove local Postgres container
	docker stop uw-alerts-pg && docker rm uw-alerts-pg

db-clear: ## Drop and recreate the dev database (destructive)
db-clear:
	docker exec -i uw-alerts-pg psql -U $(DB_USER) -c "DROP DATABASE IF EXISTS $(DB_NAME);"
	docker exec -i uw-alerts-pg psql -U $(DB_USER) -c "CREATE DATABASE $(DB_NAME);"
	docker exec -i uw-alerts-pg psql -U $(DB_USER) -c "DROP DATABASE IF EXISTS $(DB_TEST);"
	docker exec -i uw-alerts-pg psql -U $(DB_USER) -c "CREATE DATABASE $(DB_TEST);"
	@echo "Databases '$(DB_NAME)' and '$(DB_TEST)' have been reset. Run 'make schema' to reapply schema."

db-shell: ## Open a psql shell into the dev database
	docker exec -it uw-alerts-pg psql -U $(DB_USER) $(DB_NAME)

schema: ## Apply database schema (creates tables and indexes)
	docker exec -i uw-alerts-pg psql -U $(DB_USER) $(DB_NAME) < scraper/db/schema.sql
	docker exec -i uw-alerts-pg psql -U $(DB_USER) -c "CREATE DATABASE $(DB_TEST);" 2>/dev/null || true
	docker exec -i uw-alerts-pg psql -U $(DB_USER) $(DB_TEST) < scraper/db/schema.sql

migrate: ## Migrate data/uw_alerts_clean.csv into the dev database
	DATABASE_URL=$(DB_URL) .venv/bin/python -m scraper.db.migrate

serve: ## Start the Flask web app (requires .env or exported env vars)
	set -a && . ./.env && set +a && cd uw-alert-web && uv run flask --app=uw-alert-web run

run: ## Run the scraper agent once (requires .env or exported env vars)
	set -a && . ./.env && set +a && .venv/bin/python -m scraper.scraper_agent

dry-run: ## Run the scraper agent in dry-run mode (no DB writes)
	set -a && . ./.env && DRY_RUN=true .venv/bin/python -m scraper.scraper_agent

test: ## Run Flask app unit tests
	uv run poe test

test-scraper: ## Run scraper unit tests (no DB required)
	.venv/bin/pytest scraper/tests/ --ignore=scraper/tests/test_schema.py --ignore=scraper/tests/test_migrate.py -v

test-scraper-full: ## Run all scraper tests including DB tests (requires make schema first)
	TEST_DATABASE_URL=$(TEST_DB_URL) .venv/bin/pytest scraper/tests/ -v

batch-history: ## Scrape all 19 blog pages oldest-first and write to DB (idempotent)
	set -a && . ./.env && set +a && .venv/bin/python -m scraper.batch_history

batch-history-dry: ## Dry run of full history scrape — logs what would be written, no DB writes
	set -a && . ./.env && DRY_RUN=true .venv/bin/python -m scraper.batch_history

seed: ## Seed an empty DB with full history (skips if incidents table already populated)
	set -a && . ./.env && set +a && \
	  COUNT=$$(.venv/bin/python -c "import psycopg2,os; c=psycopg2.connect(os.environ['DATABASE_URL']); cur=c.cursor(); cur.execute('SELECT COUNT(*) FROM incidents'); print(cur.fetchone()[0])"); \
	  if [ "$$COUNT" = "0" ]; then \
	    echo "Database is empty — running full history import..."; \
	    .venv/bin/python -m scraper.batch_history; \
	  else \
	    echo "Database already contains $$COUNT incident(s). Run 'make batch-history' to force re-import."; \
	  fi

audit: ## Print a data quality audit report for the dev database
	set -a && . ./.env && set +a && .venv/bin/python -m scraper.audit

lint: ## Lint scraper code with ruff
	.venv/bin/ruff check scraper/
