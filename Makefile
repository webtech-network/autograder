# Development and verification commands. CI runs these same targets
# (.github/workflows/verify.yml); `make help` lists them.

PYTHON ?= python
# Tests import `tests` and `examples` from the repository root.
export PYTHONPATH := $(CURDIR)$(if $(PYTHONPATH),:$(PYTHONPATH))

.PHONY: help install verify lint contracts docs test test-web test-postgres test-integration test-e2e images sandbox-build-all sandbox-build-python sandbox-build-java sandbox-build-node sandbox-build-cpp sandbox-clean docs-serve start-autograder examples-demo

help: ## Show this list
	@echo "Usage: make <target>"
	@awk 'BEGIN {FS = ":.*## "} /^##@/ {printf "\n%s\n", substr($$0, 5)} /^[a-z][a-z0-9-]*:.*## / {printf "  make %-22s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

##@ Setup

install: ## Install runtime, test, docs and lint dependencies
	$(PYTHON) -m pip install -r requirements.txt -r requirements-docs.txt "pylint~=4.1.3"

##@ Verification paths

verify: lint contracts docs test test-web ## Hermetic core/library path (no Docker, no database)

lint: ## Pylint the shipped packages, scripts and examples (.pylintrc)
	$(PYTHON) -m pylint -j 0 autograder web sandbox_manager execution_host github_action scripts examples submission_contract.py

contracts: ## Check that checked-in JSON Schemas match the models
	$(PYTHON) scripts/generate_contract_schemas.py --check

docs: ## Check documentation links and API routes, then build the site strictly
	$(PYTHON) scripts/validate_docs.py
	$(PYTHON) -m mkdocs build --strict --quiet

test: ## Unit tests
	$(PYTHON) -m pytest tests/unit/

test-web: ## HTTP tests on SQLite (the PostgreSQL tier is excluded)
	$(PYTHON) -m pytest tests/web/ -m "not postgres"

##@ Docker and database tiers

test-postgres: ## PostgreSQL guarantees; fails unless TEST_POSTGRES_URL is set
	$(PYTHON) -m pytest tests/web/ -m postgres

test-integration: sandbox-build-all ## Real Docker sandboxes (builds sandbox images)
	$(PYTHON) -m pytest tests/integration/

test-e2e: sandbox-build-all ## API process with real Docker sandboxes
	./scripts/run_e2e_tests.sh

images: ## Build the API, sandbox manager and Action images from this checkout
	docker build -t autograder-api:local -f Dockerfile.api .
	docker build -t autograder-sandbox-manager:local -f Dockerfile.sandbox .
	docker build -t autograder-action:local -f Dockerfile.actions .

sandbox-build-all: sandbox-build-python sandbox-build-java sandbox-build-node sandbox-build-cpp ## Build every sandbox runtime image

sandbox-build-python: ## Build the Python sandbox image
	docker build -t sandbox-py:latest -f sandbox_manager/images/Dockerfile.python sandbox_manager/images/

sandbox-build-java: ## Build the Java sandbox image
	docker build -t sandbox-java:latest -f sandbox_manager/images/Dockerfile.java sandbox_manager/images/

sandbox-build-node: ## Build the Node.js sandbox image
	docker build -t sandbox-node:latest -f sandbox_manager/images/Dockerfile.javascript sandbox_manager/images/

sandbox-build-cpp: ## Build the C/C++ sandbox image
	docker build -t sandbox-cpp:latest -f sandbox_manager/images/Dockerfile.cpp sandbox_manager/images/

sandbox-clean: ## Remove the sandbox images
	-docker rmi sandbox-py:latest sandbox-java:latest sandbox-node:latest sandbox-cpp:latest

##@ Running locally

docs-serve: ## Serve the docs site with live reload
	$(PYTHON) -m mkdocs serve

start-autograder: sandbox-build-all ## Start PostgreSQL, the API and the sandbox manager (needs SANDBOX_API_TOKEN)
	docker compose up -d --build
	@echo "Autograder API: http://localhost:8000"

examples-demo: ## Serve the interactive demo page (needs a running API)
	cd examples/demo && $(PYTHON) serve_demo.py
