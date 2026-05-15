.DEFAULT_GOAL := help

help: ## Show available targets
	@grep -E '^[a-z_-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

infra: ## Start Postgres + Redis via docker compose
	docker compose up -d db redis

infra-stop: ## Stop docker compose services
	docker compose down

migrate: ## Apply Django migrations
	python manage.py migrate

web: ## Run the Django dev server (foreground)
	python manage.py runserver

worker: ## Run the Celery worker (foreground)
	celery -A config worker -l info

seed: ## Run the live agent against curated repos (needs LLM API access)
	python manage.py seed_research

seed-fixture: ## Populate DB with hand-crafted sample data (no LLM calls)
	python manage.py seed_fixture

load-fixture: ## Load sample data from fixtures/sample_data.json (no LLM calls)
	python manage.py loaddata fixtures/sample_data.json

dump-fixture: ## Dump current sample data to fixtures/sample_data.json
	mkdir -p fixtures
	python manage.py dumpdata \
		repos.repository research.researchsession \
		research.toolcall research.finding \
		--indent 2 --output fixtures/sample_data.json

test: ## Run pytest
	pytest

format: ## Auto-format code in place
	ruff format .

fix: ## Auto-format + auto-fix lint issues in place
	ruff check --fix .
	ruff format .

lint: ## Verify format + lint + types (read-only)
	ruff format --check .
	ruff check .
	mypy .

.PHONY: help infra infra-stop migrate web worker seed seed-fixture load-fixture dump-fixture test format fix lint
