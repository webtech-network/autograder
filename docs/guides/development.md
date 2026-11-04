# Development Guide

How to set up, run and test the repository. What each package owns, and which
package may import which, is described once in
[Responsibilities and Dependencies](../architecture/overview.md); the
contributor rules are in `AGENTS.md` at the repository root.

## Prerequisites

- **Python 3.13** (the version CI uses)
- **Docker** (sandbox images, integration and end-to-end tests)
- **PostgreSQL** (web API and `tests/web/`; `docker compose up -d postgres` is enough locally)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
make sandbox-build-all        # one image per runtime listed in sandbox_config.yml
```

## Project structure

```
autograder/          core: contracts, compilation, assessment, grading, feedback
├── autograder.py         AutograderPipeline.run (the explicit run order)
├── facade.py             evaluate_submission
├── models/               contracts/ (definition, outcome, scoring, verification,
│                         comparison, catalog), abstract/ (TestFunction, Template),
│                         capabilities, execution and process protocols, language,
│                         criteria tree
├── services/             assessment, grading, preparation, file selection,
│                         feedback/focus/report, template registry
├── template_library/     built-in evaluators
└── translations/         en and pt_br messages
sandbox_manager/     container pools, owner leases, run_process, reclaim, private control API
execution_host/      HostCapabilities composition (Docker, S3 fixtures, OpenAI)
web/                 HTTP host: auth, configs, durable jobs, delivery, deliberate execution
github_action/       Actions host
examples/            runnable definitions and trusted Python examples
tests/               unit/, web/, integration/ (Docker), e2e/ (Docker + API process)
docs/                documentation (contracts/ are normative)
archive/             historical designs and roadmaps, not current guidance
```

## Running the API locally

```bash
# Database
export DATABASE_URL=postgresql+asyncpg://autograder:autograder_password@localhost:5432/autograder
alembic -c web/alembic.ini upgrade head

# HTTP trust boundary (docs/contracts/AUTH.md): every protected route needs a bearer token
export AUTOGRADER_INTEGRATION_TOKEN=change-me-to-a-long-random-secret

# AI evaluators (optional)
export OPENAI_API_KEY=your_openai_key_here

# Local mode (the web default): the API process owns its sandbox pools directly.
# Images per language come from the runtimes: map in sandbox_config.yml.
SANDBOX_MODE=local uvicorn web.main:app --reload --port 8000
```

Remote mode runs the private sandbox control API as a separate single-worker
process and requires its shared token ([SANDBOX.md](../contracts/SANDBOX.md)):

```bash
export SANDBOX_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
python -m sandbox_manager &                 # 127.0.0.1:8001, one worker
SANDBOX_MODE=remote SANDBOX_API_URL=http://127.0.0.1:8001 uvicorn web.main:app --port 8000
```

`docker compose up -d --build` (or `make start-autograder`) starts PostgreSQL,
the API on port 8000 and the sandbox manager on the internal network only.
API docs are served at http://localhost:8000/docs.

## Running tests

These are the commands CI runs (`.github/workflows/`), from the repository root
with `PYTHONPATH=.`:

```bash
python scripts/generate_contract_schemas.py --check   # checked-in JSON Schemas match the models
pytest tests/unit/                                    # make test
TEST_POSTGRES_URL=postgresql+asyncpg://... pytest tests/web/
make test-integration                                 # real Docker sandboxes
make test-e2e                                         # API process + Docker
python scripts/validate_docs.py && mkdocs build --strict   # documentation (requirements-docs.txt)
pylint <changed .py files>                            # CI lints the files a push changes
```

`tests/unit/test_architecture.py` checks dependency direction, that discovery and
the documented examples agree with the registry, and the extension path.

## Making changes

### Adding an evaluator

Follow [Adding an evaluator](../architecture/extending.md): implementation,
parameter contract, registration and tests, with runnable static and execution
examples. A built-in evaluator is registered in its template under
`autograder/template_library/` (new built-in templates are added to
`autograder/services/template_library_service.py`); trusted callers pass
`templates={identifier: instance}` instead.

### Adding a language or runtime

Follow "Change surface" in [LANGUAGES.md](../contracts/LANGUAGES.md): the
language list lives only in `autograder/models/language.py`; images are host
configuration (`sandbox_config.yml` `runtimes:`).

### Changing the run order

For cross-cutting execution changes, update the explicit call sequence in
`autograder/autograder.py`. Pass typed inputs and return values directly.
Keep required assessment failures separate from optional enrichment failures,
and close owned sessions before constructing the terminal outcome.
Do not add step registries or store intermediate artifacts in diagnostic events.
See [the grading flow](../core/pipeline-architecture.md).

### Changing an HTTP route

Routes live in `web/api/v1/`, request/response schemas in `web/schemas/`, and
the operations they call in `web/service/`. Routes translate HTTP envelopes and
errors only ([JOBS.md](../contracts/JOBS.md)); every route outside the explicit
public set (health, readiness, the static catalog) goes through the trust boundary in [AUTH.md](../contracts/AUTH.md). Update
[API.md](../API.md); `scripts/validate_docs.py` checks it against the routes.

### Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`,
`fix:`, `docs:`, `refactor:`, `test:`, `chore:`). See
[CONTRIBUTING.md](https://github.com/webtech-network/autograder/blob/main/CONTRIBUTING.md)
for the issue and pull request workflow.

## Debugging

### Grading runs

`evaluate_submission(..., observer=events.append)` and `pipeline.run(submission,
observer=...)` accept an optional observer that receives frozen [diagnostic observations](../architecture/pipeline_execution_tracking.md)
(no grading data). The terminal outcome's `error` carries a safe code and
message for failed runs.

### Sandboxes

```bash
# Control API pools, quarantined removals and handle counts (remote mode)
curl -H "Authorization: Bearer $SANDBOX_API_TOKEN" http://127.0.0.1:8001/stats

# Sandbox containers with their owner leases and liveness
python -m sandbox_manager.reclaim

# Logs of one container
docker logs <container_id>
```

Containers whose owner is not provably dead are never removed automatically;
see "Owner leases and orphan reclamation" in [SANDBOX.md](../contracts/SANDBOX.md).

### Database

```bash
docker compose exec postgres psql -U autograder
```

## Sandbox pool tuning

```yaml
# sandbox_config.yml
general:
  pool_size: 5          # warm containers per language
  scale_limit: 20       # maximum containers per language (quarantined ones count)
  idle_timeout: 300
runtimes:               # only listed languages get a pool
  python: ghcr.io/webtech-network/autograder-sandbox-python:<tag>   # make sandbox-list
```

## Troubleshooting

- **Sandbox containers will not start**: check `docker info`, and confirm the
  language is listed under `runtimes:` (an unlisted language fails with
  `RUNTIME_UNAVAILABLE`).
- **`RuntimeImageError` at startup**: the configured image is not on this Docker
  host, or its `autograder.runtime.languages` label does not list the language.
  Run `docker pull <image>` for the published references, or
  `make sandbox-build-all` to build this checkout's images under the same
  references. Images are never pulled automatically.
- **401 from the API**: set `AUTOGRADER_INTEGRATION_TOKEN` and send
  `Authorization: Bearer <token>`.
- **Remote sandbox manager refuses to start**: set `SANDBOX_API_TOKEN` (or
  `SANDBOX_API_ALLOW_UNAUTHENTICATED=true` for local development only).
