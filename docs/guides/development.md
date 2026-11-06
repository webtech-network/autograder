# Development Guide

The one place for setting up, running and verifying the repository. What each
package owns, and which package may import which, is described once in
[Responsibilities and Dependencies](../architecture/overview.md); the
contributor rules are in `AGENTS.md` at the repository root. `make help` lists
every command below.

## Setup

- **[uv](https://docs.astral.sh/uv/)**. It installs **Python 3.13**, the only
  supported version (`requires-python` in `pyproject.toml`; CI uses the patch
  release in `.tool-versions`), when it is missing.
- **GNU Make**
- **Docker** only for the Docker tiers, the sandbox images and running the API
- **PostgreSQL** only for the PostgreSQL tier and the compose stack

```bash
make install                  # uv sync --locked: .venv with the project, test, lint and docs tools
make verify                   # hermetic check: no Docker, no database
```

The `make` targets run Python through `uv run --locked`; inside an activated
environment of your own, pass `PYTHON=python`. Outside `make`, run commands with
`uv run` (for example `uv run pytest tests/unit/`) or after
`source .venv/bin/activate`.

`pyproject.toml` declares one distribution (`autograder`, `web`, `sandbox_manager`,
`execution_host`, `github_action`) and its dependencies; `uv.lock` pins every
package. Runtime dependencies are separate from development tools:

| Selection | Contents | Used by |
| --- | --- | --- |
| `dependencies` | engine, execution host, GitHub Action | Action image |
| `server` extra | FastAPI, Uvicorn, SQLAlchemy, Alembic, database drivers | API and sandbox manager images |
| `dev` group (`test`, `lint`, `docs`) | pytest, pylint, MkDocs | contributors and CI, never images |

Change dependencies with `uv add` / `uv remove` (or edit `pyproject.toml` and run
`uv lock`) and commit both files. `make install` (and therefore CI) runs
`uv sync --locked`, which fails when the two disagree. `tests/unit/test_packaging.py`
builds the wheel, imports every module from it outside the checkout and checks that
the declared runtime dependencies are exactly the imported ones.

## Verification

CI ([`verify.yml`](https://github.com/webtech-network/autograder/blob/main/.github/workflows/verify.yml))
runs exactly these targets on every pull request and on `main`, and deploys the
API only after all of them pass for that commit and only while it is still
the head of `main`. Run the same command locally
before opening a pull request. `make verify` stops at the first failing step;
`make -k verify` runs every step and reports all failures. `make lint` fails on
any pylint error (`fail-on` in `.pylintrc`), whatever the repository score. It
runs in one process: parallel pylint (`-j`) reports spurious `E1136` errors on
the SQLAlchemy models depending on how modules are split across workers. It
covers the shipped packages, `scripts/` and `examples/`, not `tests/`, which still
has pylint false positives to resolve first.

| Command | Needs | Runs |
| --- | --- | --- |
| `make verify` | Python | The **core/library path**: `lint`, `contracts` (checked-in JSON Schemas match the models), `docs` (link and API-route check, strict MkDocs build), `test` (unit) and `test-web` (HTTP on SQLite). Under a minute. |
| `make test-postgres` | `TEST_POSTGRES_URL` | PostgreSQL claims, publication fencing and concurrent idempotency. Without the URL these tests **error**; they never skip. The role must be able to `CREATE DATABASE` (migration tests). |
| `make test-integration` | Docker | Real sandboxes; builds the sandbox images first. Suites run under gVisor when Docker offers `runsc` (else runc; `AUTOGRADER_TEST_RUNTIME` overrides). The per-runtime isolation suites are left to `make test-isolation`. `make gvisor-install` (sudo) installs the pinned gVisor release. |
| `make test-isolation` | Docker | The per-runtime isolation suites (hostile submissions, sandbox attribution), under every runtime Docker offers; CI runs it after `make gvisor-install`, so under gVisor and runc. |
| `make test-e2e` | Docker | An API process with real sandboxes. |
| `make images` | Docker | Builds the API, sandbox manager and Action images from the checkout. |

The PostgreSQL tier needs a disposable database; every test creates and drops
its own schema:

```bash
docker run -d --rm --name autograder-test-postgres -p 127.0.0.1:5433:5432 \
  -e POSTGRES_USER=autograder -e POSTGRES_PASSWORD=local-test-only -e POSTGRES_DB=autograder \
  postgres:17-alpine
TEST_POSTGRES_URL=postgresql+asyncpg://autograder:local-test-only@127.0.0.1:5433/autograder make test-postgres
```

The HTTP service path (the compose stack built from the commit, with
migrations and remote sandboxes) and the packaged GitHub Action path will each
become one more `make` target and CI job; until then the Docker tiers above
cover them.

`tests/unit/test_architecture.py` checks dependency direction, that discovery and
the documented examples agree with the registry, and the extension path.
`tests/unit/test_verification_frame.py` checks that `make help`, the docs and
CI name only existing targets, and that deployment waits for every
verification job.

### Documentation site

`make docs-serve` previews the MkDocs Material site at http://127.0.0.1:8000
with live reload; `make docs` is the strict build CI runs, which turns broken
navigation or links into errors.

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
```

## Running the API locally

```bash
# Sandbox images, one per runtime listed in sandbox_config.yml
make sandbox-build-all

# Database
docker compose up -d postgres
export DATABASE_URL=postgresql+asyncpg://autograder:autograder_password@localhost:5432/autograder
make db-upgrade               # the API never creates tables; see JOBS.md "Deployment and migration"

# HTTP trust boundary (docs/contracts/AUTH.md): every protected route needs a bearer token
export AUTOGRADER_INTEGRATION_TOKEN=change-me-to-a-long-random-secret

# AI evaluators (optional)
export OPENAI_API_KEY=your_openai_key_here

# Local mode (the web default): the API process owns its sandbox pools directly.
# Images per language come from the runtimes: map in sandbox_config.yml.
SANDBOX_MODE=local uvicorn web.main:app --reload --port 8000
```

**Without gVisor.** The shipped `sandbox_config.yml` requires gVisor
(`general.runtime: runsc`). If `docker info` does not list `runsc`, install it
(`make gvisor-install`; Linux, sudo) or choose runc deliberately with a
development copy: `sed 's/runtime: runsc/runtime: runc/' sandbox_config.yml >
sandbox_config.dev.yml` (ignored by git), then
`export SANDBOX_CONFIG_FILE=$PWD/sandbox_config.dev.yml`. Otherwise the local API
starts but fails every execution grading with `IsolationRuntimeError`, and the
control service (`python -m sandbox_manager`, the compose `sandbox-manager`)
refuses to start. For compose, give `sandbox-manager` the copy in a
`docker-compose.override.yml`: mount `./sandbox_config.dev.yml:/config/sandbox.yml:ro`
and set `SANDBOX_CONFIG_FILE: /config/sandbox.yml`.

Remote mode runs the private sandbox control API as a separate single-worker
process and requires its shared token ([SANDBOX.md](../contracts/SANDBOX.md)):

```bash
export SANDBOX_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
python -m sandbox_manager &                 # 127.0.0.1:8001, one worker
SANDBOX_MODE=remote SANDBOX_API_URL=http://127.0.0.1:8001 uvicorn web.main:app --port 8000
```

`docker compose up -d --build` (or `make start-autograder`) starts PostgreSQL,
migrates it in the one-shot `migrate` service, then starts the API on port 8000
and the sandbox manager on the internal network only.
API docs are served at http://localhost:8000/docs.

## Making changes

### Adding an evaluator

Follow [Adding an evaluator](../architecture/extending.md): implementation,
parameter contract, registration and tests, with runnable static and execution
examples. A built-in evaluator is added to its template under
`autograder/template_library/` (new built-in templates are one entry in
`BUILTIN_TEMPLATES` there) and follows the built-in checklist; trusted callers
pass `templates={identifier: instance}` instead.

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

### Changing the database schema

Change the model, then generate and review a revision against a database at
head: `make db-migrate MSG="describe the change"`. `tests/web/test_migrations.py`
fails until `upgrade head` from empty equals the models again, and checks the
downgrade/upgrade round trip.

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

## Sandbox budget tuning

```yaml
# sandbox_config.yml
general:
  max_sandboxes: 8      # host-wide budget N for all languages, grading and /execute;
                        # creating, active, closing and quarantined sandboxes count
  pool_size: 1          # warm idle containers per language (outside N)
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
