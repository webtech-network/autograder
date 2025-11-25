# Makefile for Autograder Development
# Simplifies common development tasks

.PHONY: help install install-dev test test-cov lint format type-check security clean build docs run-api docker-build

# Default target
help:
	@echo "Available commands:"
	@echo "  make install        - Install production dependencies"
	@echo "  make run-api        - Run API server locally"
	@echo "  make docker-build   - Build Docker image"

# Installation
install:
	pip install -r requirements.txt

# Running
run-api:
	uvicorn connectors.adapters.api.api_entrypoint:app --reload --host 0.0.0.0 --port 8000

# Docker
docker-build:
	docker build -t autograder:latest -f Dockerfile .

docker-build-api:
	docker build -t autograder-api:latest -f Dockerfile.api .

docker-run-api:
	docker run -p 8000:8000 autograder-api:latest



