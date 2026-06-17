# Local dev database (Docker)
DB_NAME     = uw_alerts_dev
DB_TEST     = uw_alerts_test
DB_USER     = postgres
DB_PASSWORD = postgres
DB_PORT     = 5432
DB_URL      = postgres://$(DB_USER):$(DB_PASSWORD)@localhost:$(DB_PORT)/$(DB_NAME)
TEST_DB_URL = postgres://$(DB_USER):$(DB_PASSWORD)@localhost:$(DB_PORT)/$(DB_TEST)

.PHONY: db-up db-down db-shell schema migrate run dry-run test test-scraper lint help

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

db-shell: ## Open a psql shell into the dev database
	docker exec -it uw-alerts-pg psql -U $(DB_USER) $(DB_NAME)

schema: ## Apply database schema (creates tables and indexes)
	docker exec -i uw-alerts-pg psql -U $(DB_USER) $(DB_NAME) < scraper/db/schema.sql
	docker exec -i uw-alerts-pg psql -U $(DB_USER) -c "CREATE DATABASE $(DB_TEST);" 2>/dev/null || true
	docker exec -i uw-alerts-pg psql -U $(DB_USER) $(DB_TEST) < scraper/db/schema.sql

migrate: ## Migrate data/uw_alerts_clean.csv into the dev database
	DATABASE_URL=$(DB_URL) .venv/bin/python -m scraper.db.migrate

run: ## Run the scraper agent once (requires .env or exported env vars)
	.venv/bin/python scraper/scraper_agent.py

dry-run: ## Run the scraper agent in dry-run mode (no DB writes)
	DRY_RUN=true .venv/bin/python scraper/scraper_agent.py

test: ## Run Flask app unit tests
	uv run poe test

test-scraper: ## Run scraper unit tests (no DB required)
	.venv/bin/pytest scraper/tests/ --ignore=scraper/tests/test_schema.py --ignore=scraper/tests/test_migrate.py -v

test-scraper-full: ## Run all scraper tests including DB tests (requires make schema first)
	TEST_DATABASE_URL=$(TEST_DB_URL) .venv/bin/pytest scraper/tests/ -v

lint: ## Lint scraper code with ruff
	.venv/bin/ruff check scraper/
