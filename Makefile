# =============================================================================
# StigmergiAgentic — Makefile
# Sprint 2.5 — Docker shortcuts for tests & migrations
# =============================================================================

.PHONY: docker-build docker-test docker-test-cov docker-migrate docker-shell help

IMAGE_NAME := stigmergic-poc

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# --------------- Docker commands ---------------

docker-build: ## Build the Docker image
	docker compose build

docker-test: ## Run full test suite in Docker
	docker compose run --rm test

docker-test-cov: ## Run tests with coverage report in Docker
	docker compose run --rm test-cov

docker-migrate: ## Run migration in Docker (usage: make docker-migrate REPO=<url>)
	REPO=$(REPO) docker compose run --rm migrate

docker-shell: ## Open an interactive shell in the Docker container
	docker compose run --rm shell

# --------------- Local commands (uv) ---------------

test: ## Run tests locally with uv
	uv run pytest tests/ -v

test-cov: ## Run tests with coverage locally
	uv run pytest tests/ --cov --cov-report=term-missing -v

lint: ## Run ruff linter
	ruff check . --fix --exclude tests/fixtures

format: ## Format code with black
	black . --exclude '/tests/fixtures/'
