.PHONY: help build run stop restart logs test lint format clean docker-build docker-push deploy health

# Variables
DOCKER_IMAGE = fastapi-bot
DOCKER_TAG = latest
CONTAINER_NAME = telegram-bot-fastapi

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies
	pip install -r requirements.txt

dev-install: ## Install development dependencies
	pip install -r requirements.txt
	pip install pytest pytest-cov pytest-asyncio flake8 black isort pylint mypy

build: ## Build Docker image
	docker build -t $(DOCKER_IMAGE):$(DOCKER_TAG) .

build-prod: ## Build production Docker image
	docker build -f Dockerfile.prod -t $(DOCKER_IMAGE):$(DOCKER_TAG) .

run: ## Run application locally
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

docker-run: ## Run Docker container
	docker-compose up -d

docker-run-prod: ## Run production Docker container
	docker-compose -f docker-compose.prod.yml up -d

stop: ## Stop Docker containers
	docker-compose down

restart: ## Restart Docker containers
	docker-compose restart

logs: ## View Docker logs
	docker-compose logs -f bot

shell: ## Open shell in running container
	docker exec -it $(CONTAINER_NAME) /bin/bash

test: ## Run tests
	pytest --cov=app --cov-report=term-missing

test-verbose: ## Run tests with verbose output
	pytest -v --cov=app --cov-report=term-missing --cov-report=html

lint: ## Run linters
	@command -v flake8 >/dev/null 2>&1 || { echo "flake8 not installed. Run: pip install flake8"; exit 1; }
	flake8 app --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 app --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

format: ## Format code
	@command -v black >/dev/null 2>&1 || { echo "black not installed. Run: pip install black"; exit 1; }
	black app
	@command -v isort >/dev/null 2>&1 && isort app || echo "isort not installed (optional). Run: pip install isort"

format-check: ## Check code formatting
	@command -v black >/dev/null 2>&1 || { echo "black not installed. Run: pip install black"; exit 1; }
	black --check app
	@command -v isort >/dev/null 2>&1 && isort --check-only app || echo "isort not installed (optional). Run: pip install isort"

type-check: ## Run type checking
	mypy app --ignore-missing-imports

security-check: ## Run security checks
	bandit -r app
	safety check

clean: ## Clean up temporary files
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.coverage" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +

docker-clean: ## Clean up Docker resources
	docker-compose down -v
	docker system prune -f

health: ## Check application health
	curl -f http://localhost:8000/health || echo "Health check failed"

webhook-check: ## Check webhook status
	python scripts/check_webhook.py

webhook-register: ## Register webhook
	python scripts/register_webhook.py

webhook-delete: ## Delete webhook
	python scripts/delete_webhook.py

ci: lint test ## Run CI checks locally (run 'make format' first to auto-format code)

all: clean install format lint test build ## Run all checks and build
