# Makefile for Autograder Development
# Simplifies common development tasks

.PHONY: help install install-dev test test-cov lint format type-check security clean build docs run-api run-api-tests examples-demo start-autograder docker-build sandbox-build sandbox-build-all sandbox-clean db-migrate db-upgrade db-downgrade db-current db-history db-init db-reset

# Default target
help:
	@echo "Available commands:"
	@echo "  make install             - Install production dependencies"
	@echo "  make examples-demo       - Run interactive demo webpage"
	@echo "  make start-autograder    - Start the Autograder API server"
	@echo ""
	@echo "Database Migrations:"
	@echo "  make db-upgrade          - Apply all pending migrations"
	@echo "  make db-downgrade        - Rollback last migration"
	@echo "  make db-current          - Show current migration version"
	@echo "  make db-history          - Show migration history"
	@echo "  make db-migrate MSG=desc - Create new migration with description"
	@echo "  make db-init             - Initialize database (upgrade to head)"
	@echo "  make db-reset            - Reset database (downgrade to base, then upgrade)"
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

# Database Migrations
db-upgrade:
	@echo "📦 Applying database migrations..."
	alembic upgrade head
	@echo "✅ Database migrations applied successfully!"

db-downgrade:
	@echo "⏪ Rolling back last migration..."
	alembic downgrade -1
	@echo "✅ Migration rolled back successfully!"

db-current:
	@echo "📍 Current migration version:"
	alembic current

db-history:
	@echo "📜 Migration history:"
	alembic history --verbose

db-migrate:
	@if [ -z "$(MSG)" ]; then \
		echo "❌ Error: Please provide a message with MSG=your_description"; \
		echo "Example: make db-migrate MSG='add user table'"; \
		exit 1; \
	fi
	@echo "📝 Creating new migration: $(MSG)"
	alembic revision --autogenerate -m "$(MSG)"
	@echo "✅ Migration file created! Review it before applying."

db-init:
	@echo "🚀 Initializing database..."
	alembic upgrade head
	@echo "✅ Database initialized successfully!"

db-reset:
	@echo "⚠️  WARNING: This will reset the entire database!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		alembic downgrade base; \
		alembic upgrade head; \
		echo "✅ Database reset complete!"; \
	else \
		echo "❌ Reset cancelled"; \
	fi

examples-demo:
	@echo "🚀 Starting Autograder Interactive Demo..."
	@echo "   Server: http://localhost:8080"
	@echo "   Press Ctrl+C to stop"
	@echo ""
	cd examples/demo && python serve_demo.py

start-autograder:
	@echo "🚀 Starting Autograder API server..."
	make sandbox-build-all && docker compose up -d --build
	@echo "✅ Autograder API server is running at http://localhost:8080"


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



