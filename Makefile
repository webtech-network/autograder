# Development and verification commands. CI runs these same targets
# (.github/workflows/verify.yml); `make help` lists them.

# Commands run in the locked .venv (`make install`); override PYTHON to use
# another interpreter, e.g. `make verify PYTHON=python` inside an activated venv.
PYTHON ?= uv run --locked python

.PHONY: help install verify lint contracts docs test test-web test-postgres test-integration test-e2e images test-images action-publish sandbox-build-all sandbox-build-python sandbox-build-java sandbox-build-node sandbox-build-cpp sandbox-list sandbox-clean db-upgrade db-downgrade db-current db-history db-migrate docs-serve start-autograder examples-demo

help: ## Show this list
	@echo "Usage: make <target>"
	@awk 'BEGIN {FS = ":.*## "} /^##@/ {printf "\n%s\n", substr($$0, 5)} /^[a-z][a-z0-9-]*:.*## / {printf "  make %-22s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

##@ Setup

install: ## Create .venv from uv.lock: the project with its server extra, test, lint and docs tools
	uv sync --locked

##@ Verification paths

verify: lint contracts docs test test-web ## Hermetic core/library path (no Docker, no database)

lint: ## Pylint the shipped packages, scripts and examples, serially (.pylintrc)
	$(PYTHON) -m pylint autograder web sandbox_manager execution_host github_action scripts examples

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
	PYTHON='$(PYTHON)' ./scripts/run_e2e_tests.sh

# Local names of the service and Action images: $(IMAGE_PREFIX)-<name>:$(IMAGE_TAG).
IMAGE_PREFIX ?= autograder
IMAGE_TAG ?= local

images: ## Build the API, sandbox manager and Action images from this checkout
	docker build -t $(IMAGE_PREFIX)-api:$(IMAGE_TAG) -f Dockerfile.api .
	docker build -t $(IMAGE_PREFIX)-sandbox-manager:$(IMAGE_TAG) -f Dockerfile.sandbox .
	docker build -t $(IMAGE_PREFIX)-action:$(IMAGE_TAG) -f Dockerfile.actions .

test-images: images ## Contents, context leaks and Action grading of exactly those images
	AUTOGRADER_IMAGE_PREFIX='$(IMAGE_PREFIX)' AUTOGRADER_IMAGE_TAG='$(IMAGE_TAG)' $(PYTHON) -m pytest tests/images/

action-publish: ## Release the tested Action image under the version action.yml pins (CI, main only)
	$(PYTHON) -m scripts.action_image publish $(IMAGE_PREFIX)-action:$(IMAGE_TAG)

# The versioned runtime images named in sandbox_config.yml (scripts/sandbox_images.py).
SANDBOX_IMAGES = $(PYTHON) scripts/sandbox_images.py

sandbox-build-all: ## Build every sandbox runtime image under its versioned reference
	$(SANDBOX_IMAGES) build

sandbox-build-python: ## Build the Python sandbox image
	$(SANDBOX_IMAGES) build python

sandbox-build-java: ## Build the Java sandbox image
	$(SANDBOX_IMAGES) build java

sandbox-build-node: ## Build the Node.js sandbox image
	$(SANDBOX_IMAGES) build node

sandbox-build-cpp: ## Build the C/C++ sandbox image
	$(SANDBOX_IMAGES) build cpp

sandbox-list: ## Show the runtime image each language uses
	@$(SANDBOX_IMAGES) list

sandbox-clean: ## Remove the sandbox images
	-docker rmi $$($(SANDBOX_IMAGES) list | cut -d' ' -f2 | sort -u)

##@ Database migrations (DATABASE_URL selects the database)

ALEMBIC = $(PYTHON) -m alembic -c web/alembic.ini

db-upgrade: ## Apply all pending migrations (the API never creates tables)
	$(ALEMBIC) upgrade head

db-downgrade: ## Roll back the last migration
	$(ALEMBIC) downgrade -1

db-current: ## Show the current migration revision
	$(ALEMBIC) current

db-history: ## Show the migration history
	$(ALEMBIC) history --verbose

db-migrate: ## Autogenerate a migration against head: make db-migrate MSG="describe the change"
	@if [ -z "$(MSG)" ]; then echo 'Usage: make db-migrate MSG="describe the change"'; exit 1; fi
	$(ALEMBIC) revision --autogenerate -m "$(MSG)"

##@ Running locally

docs-serve: ## Serve the docs site with live reload
	$(PYTHON) -m mkdocs serve

start-autograder: sandbox-build-all ## Start PostgreSQL, the API and the sandbox manager (needs SANDBOX_API_TOKEN)
	docker compose up -d --build
	@echo "Autograder API: http://localhost:8000"

examples-demo: ## Serve the interactive demo page (needs a running API)
	cd examples/demo && $(PYTHON) serve_demo.py
