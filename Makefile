.PHONY: help install install-dev test test-cov lint format security clean docker-build docker-run pre-commit

# Default target
help:
	@echo "Application Manager Service - Development Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make install        Install production dependencies"
	@echo "  make install-dev    Install all dependencies (dev, test, tracing)"
	@echo "  make pre-commit     Install pre-commit hooks"
	@echo ""
	@echo "Development:"
	@echo "  make run            Run the application locally"
	@echo "  make worker         Run the background worker"
	@echo "  make test           Run tests"
	@echo "  make test-cov       Run tests with coverage report"
	@echo "  make lint           Run linters (ruff, mypy)"
	@echo "  make format         Format code (black, isort)"
	@echo "  make security       Run security checks (bandit)"
	@echo "  make check          Run all checks (lint, security, test)"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build   Build Docker image"
	@echo "  make docker-run     Run Docker container"
	@echo "  make docker-up      Start all services with docker-compose"
	@echo "  make docker-down    Stop all services"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean          Remove cache and build artifacts"
	@echo "  make db-indexes     Create database indexes"

# =============================================================================
# Setup
# =============================================================================

install:
	poetry install --only main

install-dev:
	poetry install --with dev,test,tracing

pre-commit:
	pip install pre-commit
	pre-commit install
	pre-commit install --hook-type commit-msg

# =============================================================================
# Development
# =============================================================================

run:
	poetry run uvicorn app.main:app --reload --port 8009

worker:
	poetry run python -m app.workers.application_worker

test:
	poetry run pytest tests/ -v

test-cov:
	poetry run pytest tests/ \
		--cov=app \
		--cov-report=term-missing \
		--cov-report=html \
		--cov-report=xml \
		-v

lint:
	poetry run ruff check app/
	poetry run mypy app/ --ignore-missing-imports

format:
	poetry run black app/ tests/
	poetry run ruff check app/ --fix

security:
	poetry run bandit -r app/ -ll -ii -x tests/

check: lint security test

# =============================================================================
# Docker
# =============================================================================

docker-build:
	docker build -t application-manager-service:latest .

docker-run:
	docker run -p 8009:8000 \
		-e MONGODB=mongodb://host.docker.internal:27017 \
		-e RABBITMQ_URL=amqp://guest:guest@host.docker.internal:5672/ \
		application-manager-service:latest

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

# =============================================================================
# Utilities
# =============================================================================

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	find . -type f -name "coverage.xml" -delete 2>/dev/null || true
	find . -type f -name "junit.xml" -delete 2>/dev/null || true

db-indexes:
	poetry run python -c "import asyncio; from app.core.database import init_database; asyncio.run(init_database())"

# =============================================================================
# CI helpers
# =============================================================================

ci-lint:
	ruff check app/ --output-format=github
	black --check --diff app/

ci-test:
	pytest tests/ \
		--cov=app \
		--cov-report=xml \
		--junitxml=junit.xml \
		-v
