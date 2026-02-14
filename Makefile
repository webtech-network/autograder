# Makefile for Autograder Development
# Simplifies common development tasks

.PHONY: help install install-dev test test-cov lint format type-check security clean build docs run-api run-api-tests docker-build sandbox-build sandbox-build-all sandbox-clean

# Default target
help:
	@echo "Available commands:"
	@echo "  make install             - Install production dependencies"
	@echo "  make run-api             - Run API server locally"
	@echo "  make run-api-tests       - Run API integration tests"
	@echo "  make docker-build        - Build Docker image"
	@echo ""
	@echo "Sandbox Management:"
	@echo "  make sandbox-build-all   - Build all sandbox images"
	@echo "  make sandbox-build-python- Build Python sandbox image"
	@echo "  make sandbox-build-java  - Build Java sandbox image"
	@echo "  make sandbox-build-node  - Build Node.js sandbox image"
	@echo "  make sandbox-build-cpp   - Build C++ sandbox image"
	@echo "  make sandbox-clean       - Remove all sandbox images"
	@echo "  make sandbox-test        - Run sandbox integration tests"

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

# Sandbox Management
sandbox-build-all: sandbox-build-python sandbox-build-java sandbox-build-node sandbox-build-cpp
	@echo "✅ All sandbox images built successfully!"

sandbox-build-python:
	@echo "Building Python sandbox image..."
	docker build -t sandbox-py:latest -f sandbox_manager/images/Dockerfile.python sandbox_manager/images/

sandbox-build-java:
	@echo "Building Java sandbox image..."
	docker build -t sandbox-java:latest -f sandbox_manager/images/Dockerfile.java sandbox_manager/images/

sandbox-build-node:
	@echo "Building Node.js sandbox image..."
	docker build -t sandbox-node:latest -f sandbox_manager/images/Dockerfile.javascript sandbox_manager/images/

sandbox-build-cpp:
	@echo "Building C++ sandbox image..."
	docker build -t sandbox-cpp:latest -f sandbox_manager/images/Dockerfile.cpp sandbox_manager/images/

sandbox-clean:
	@echo "Removing sandbox images..."
	-docker rmi sandbox-py:latest
	-docker rmi sandbox-java:latest
	-docker rmi sandbox-node:latest
	-docker rmi sandbox-cpp:latest
	@echo "✅ Sandbox images removed"

sandbox-test:
	@echo "Running sandbox integration tests..."
	python tests/playroom/sandbox_examples.py

sandbox-list:
	@echo "Sandbox images:"
	@docker images | grep sandbox- || echo "No sandbox images found"



