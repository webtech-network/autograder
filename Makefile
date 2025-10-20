# Makefile for Autograder Development
# Simplifies common development tasks

.PHONY: help install install-dev test test-cov lint format type-check security clean build docs run-api run-api-tests docker-build

# Default target
help:
	@echo "Available commands:"
	@echo "  make install        - Install production dependencies"
	@echo "  make install-dev    - Install development dependencies"
	@echo "  make setup-hooks    - Install pre-commit hooks"
	@echo "  make test           - Run tests"
	@echo "  make test-cov       - Run tests with coverage report"
	@echo "  make test-unit      - Run only unit tests"
	@echo "  make test-integration - Run only integration tests"
	@echo "  make lint           - Run all linters"
	@echo "  make format         - Format code with black and isort"
	@echo "  make type-check     - Run mypy type checking"
	@echo "  make security       - Run security checks"
	@echo "  make clean          - Clean build artifacts"
	@echo "  make build          - Build distribution packages"
	@echo "  make docs           - Build documentation"
	@echo "  make run-api        - Run API server locally"
	@echo "  make run-api-tests  - Run API integration tests (optionally specify template: web, api, io, essay, custom, all)"
	@echo "  make docker-build   - Build Docker image"
	@echo "  make all            - Format, lint, type-check, and test"

# Installation
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install -r requirements-dev.txt

setup-hooks:
	pre-commit install
	@echo "✓ Pre-commit hooks installed"

# Testing
test:
	pytest tests/ -v

test-cov:
	pytest tests/ --cov=autograder --cov=connectors --cov-report=term-missing --cov-report=html
	@echo "Coverage report generated in htmlcov/index.html"

test-unit:
	pytest tests/ -v -m unit

test-integration:
	pytest tests/ -v -m integration

test-watch:
	pytest-watch tests/ -v

# Code quality
lint:
	@echo "Running flake8..."
	flake8 autograder connectors tests
	@echo "Running pylint..."
	pylint autograder connectors || true
	@echo "✓ Linting complete"

format:
	@echo "Sorting imports with isort..."
	isort autograder connectors tests
	@echo "Formatting code with black..."
	black autograder connectors tests
	@echo "✓ Formatting complete"

format-check:
	black --check autograder connectors tests
	isort --check-only autograder connectors tests

type-check:
	@echo "Running mypy type checker..."
	mypy autograder connectors
	@echo "✓ Type checking complete"

security:
	@echo "Running bandit security scanner..."
	bandit -r autograder connectors -c pyproject.toml
	@echo "Checking for known vulnerabilities..."
	safety check || true
	@echo "✓ Security checks complete"

# Documentation
docs:
	cd docs && make html
	@echo "Documentation built in docs/_build/html/index.html"

docs-serve:
	cd docs/_build/html && python -m http.server 8000

# Running
run-api:
	uvicorn connectors.adapters.api.api_entrypoint:app --reload --host 0.0.0.0 --port 8000

run-api-prod:
	uvicorn connectors.adapters.api.api_entrypoint:app --host 0.0.0.0 --port 8000

# API Testing
# Usage: 
#   make run-api-tests           - Run all API tests
#   make run-api-tests web       - Run only web dev tests
#   make run-api-tests api       - Run only API tests
#   make run-api-tests io        - Run only I/O tests
#   make run-api-tests essay     - Run only essay tests
#   make run-api-tests custom    - Run only custom template tests
run-api-tests:
	@if [ -z "$(filter-out $@,$(MAKECMDGOALS))" ]; then \
		echo "Running all API tests..."; \
		python test_api_requests.py --test all; \
	else \
		TEMPLATE=$(filter-out $@,$(MAKECMDGOALS)); \
		echo "Running API tests for template: $$TEMPLATE"; \
		python test_api_requests.py --test $$TEMPLATE; \
	fi

# Catch-all target to prevent "make: *** No rule to make target" errors
# when passing template names as arguments
%:
	@:

# Docker
docker-build:
	docker build -t autograder:latest -f Dockerfile .

docker-build-api:
	docker build -t autograder-api:latest -f Dockerfile.api .

docker-run-api:
	docker run -p 8000:8000 autograder-api:latest

# Build & Release
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	@echo "✓ Cleaned build artifacts"

build: clean
	python -m build
	@echo "✓ Built distribution packages in dist/"

publish-test:
	python -m twine upload --repository testpypi dist/*

publish:
	python -m twine upload dist/*

# Development workflow
all: format lint type-check test
	@echo "✓ All checks passed!"

# Quick check before commit
check: format-check lint type-check test-unit
	@echo "✓ Pre-commit checks passed!"

# Initialize development environment
dev-setup: install-dev setup-hooks
	@echo "✓ Development environment ready!"
	@echo "Run 'make test' to verify everything works"
