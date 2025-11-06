.PHONY: help lint lint-fix format type-check check test

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

lint: ## Run all checks (format, lint, type-check) without modifying files
	@echo "Checking format..."
	@uv run ruff format --check .
	@echo "Checking lint..."
	@uv run ruff check .
	@echo "Type checking..."
	@uv run pyright
	@echo "All checks passed!"

lint-fix: ## Auto-fix formatting and linting issues
	@echo "Running Ruff formatter..."
	@uv run ruff format .
	@echo "Running Ruff linter..."
	@uv run ruff check . --fix
	@echo "Running Pyright..."
	@uv run pyright
	@echo "All checks passed!"

format: ## Format code with Ruff
	@uv run ruff format .

type-check: ## Run type checking with Pyright
	@uv run pyright

check: lint ## Alias for lint

test: ## Run Django tests
	@uv run python manage.py test

# Docker targets
docker-up: ## Start Docker containers
	docker-compose up

docker-build: ## Build Docker containers
	docker-compose build

docker-down: ## Stop Docker containers
	docker-compose down

docker-logs: ## Show Docker logs
	docker-compose logs -f web

docker-lint: ## Run lint checks in Docker container
	docker-compose exec web make lint

docker-lint-fix: ## Run lint-fix in Docker container
	docker-compose exec web make lint-fix

