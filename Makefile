.PHONY: help install format lint test test-cov clean run docker-build docker-run

help:
	@echo "Available commands:"
	@echo "  make install     - Install dependencies"
	@echo "  make format      - Format code with black and isort"
	@echo "  make lint        - Run linters (flake8)"
	@echo "  make test        - Run tests"
	@echo "  make test-cov    - Run tests with coverage report"
	@echo "  make clean       - Clean up generated files"
	@echo "  make run         - Run the application locally"
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-run  - Run Docker container"

install:
	pip install -r requirements.txt
	pip install pytest pytest-cov pytest-asyncio flake8 black isort

format:
	black app tests
	isort app tests

lint:
	flake8 app --count --select=E9,F63,F7,F82 --show-source --statistics
	flake8 app --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics

test:
	pytest tests/ -v

test-cov:
	pytest tests/ --cov=app --cov-report=html --cov-report=term-missing -v
	@echo "Coverage report generated in htmlcov/index.html"

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.coverage" -delete
	rm -rf .pytest_cache htmlcov .coverage coverage.xml
	rm -rf build dist *.egg-info

run:
	python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

docker-build:
	docker build -t telegram-bot-fastapi .

docker-run:
	docker run -d --name telegram-bot-fastapi -p 8000:8000 --env-file .env telegram-bot-fastapi
