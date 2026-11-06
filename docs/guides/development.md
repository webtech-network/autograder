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
| `dependencies` | engine, execution host, GitHub Action | every image |
| `sandbox` extra | FastAPI, Uvicorn, AnyIO (the private sandbox control API) | sandbox manager image |
| `server` extra | the `sandbox` extra, SQLAlchemy, Alembic, database drivers | API image |
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
| `make verify` | Python | The **core/library path**: `lint`, `contracts` (checked-in JSON Schemas and the generated `docs/reference/` pages match the contracts), `docs` (link and API-route check, strict MkDocs build), `test` (unit) and `test-web` (HTTP on SQLite). Both test steps set `DOCKER_HOST` to an unreachable socket, so a test that contacts a Docker daemon fails here and in CI, even on a machine that has Docker. Under a minute. |
| `make test-postgres` | `TEST_POSTGRES_URL` | PostgreSQL claims, publication fencing and concurrent idempotency. Without the URL these tests **error**; they never skip. The role must be able to `CREATE DATABASE` (migration tests). |
| `make test-integration` | Docker | Real sandboxes; builds the sandbox images first. Suites run under gVisor when Docker offers `runsc` (else runc; `AUTOGRADER_TEST_RUNTIME` overrides). The per-runtime isolation suites are left to `make test-isolation`. `make gvisor-install` (sudo) installs the pinned gVisor release. |
| `make test-isolation` | Docker | The per-runtime isolation suites (hostile submissions, sandbox attribution), under every runtime Docker offers; CI runs it after `make gvisor-install`, so under gVisor and runc. |
| `make test-e2e` | Docker | An API process with real sandboxes. |
| `make test-http` | Docker, `runsc` | The **HTTP path**: builds the images, starts two `docker-compose.yml` stacks side by side from empty volumes (PostgreSQL, migrations, seeded S3 emulator, sandbox manager, API in remote mode), grades the fixture example, recovers a retained outcome receipt across an API recreate without grading again, and checks that the image rejects retired configuration. Removes the stacks, their volumes and sandboxes. |
| `make images` | Docker | Builds the API, sandbox manager and Action images from the checkout as `<IMAGE_PREFIX>-<name>:<IMAGE_TAG>` (default `autograder-<name>:local`, the names `docker-compose.yml` runs). |
| `make test-images` | Docker | Builds those images and the Python runtime, and checks exactly them ([Images](#images)), including the packaged Action grading in a sandbox on the Docker socket it is given. |
| `make action-fixtures`, `make test-action` | Docker, a GitHub runner | The `Packaged Action on a hosted runner` CI job: fixture checkouts graded by `uses: ./` (`action.yml` pointed at `Dockerfile.actions`), then each outcome, its outputs and the runner's sandboxes checked (`scripts/action_fixtures.py`). Not useful outside a workflow. |
| `make action-check` | Network, full git history | Fails unless the version `action.yml` pins is tagged in this commit's history, nothing released (`action.yml` and the Action image's inputs) changed since that tag, and its image and the runtime images it pins are anonymously pullable (asked with an empty `DOCKER_CONFIG`, so a GHCR login does not hide a private package). |

A bare `pytest` collects all of `tests/`, including `tests/integration/`,
`tests/e2e/`, `tests/stack/` and `tests/images/`, which fail rather than skip without Docker and
the images they need. Use the targets above, or name a directory
(`uv run pytest tests/unit/`).

The PostgreSQL tier needs a disposable database; every test creates and drops
its own schema:

```bash
docker run -d --rm --name autograder-test-postgres -p 127.0.0.1:5433:5432 \
  -e POSTGRES_USER=autograder -e POSTGRES_PASSWORD=local-test-only -e POSTGRES_DB=autograder \
  postgres:17-alpine
TEST_POSTGRES_URL=postgresql+asyncpg://autograder:local-test-only@127.0.0.1:5433/autograder make test-postgres
```

The packaged GitHub Action path is the `Packaged Action on a hosted runner`
CI job (`make action-fixtures`, `uses: ./`, `make test-action`); locally,
`make test-images` builds the Action image from the checkout and grades with it
on the Docker socket it is given.

`tests/unit/test_architecture.py` checks dependency direction, that discovery and
the documented examples agree with the registry, and the extension path.
`tests/unit/test_verification_frame.py` checks that `make help`, the docs and
CI name only existing targets, and that deployment and the Action release wait
for every verification job.

### Required checks

A red job blocks a merge into `main` only when the `main` ruleset
(`SINGLE_APPROVAL_BPR`, id `8901171`) requires it. The ruleset must require
every verification job of `verify.yml` by its name, from the GitHub Actions app:

- `Core path (make verify)`
- `PostgreSQL tier`
- `Service and Action images` (which runs `make action-check` into `main`)
- `Docker sandboxes (integration and e2e)`
- `Sandbox isolation under gVisor and runc`
- `HTTP path (Compose stack from this commit)`
- `Packaged Action on a hosted runner` (the Action from this commit, `uses: ./`, on `ubuntu-latest`)

The publication jobs (`Release Action image`, `Deploy API`) are skipped on pull
requests and are not required. Check the setting with:

```bash
gh api repos/webtech-network/autograder/rulesets/8901171 \
  --jq '.rules[] | select(.type == "required_status_checks") | .parameters.required_status_checks[].context'
```

It must print exactly the names above. Today it still requires `pylint` and
`pytest`, contexts no workflow produces, so no check blocks a merge into `main`
yet. Before the first merge of `refactor/363` into `main`, the repository owner
replaces them (Settings → Rules → Rulesets → `SINGLE_APPROVAL_BPR` → Require
status checks to pass) and confirms with the command above. A job added to or
renamed in `verify.yml` changes this list and the ruleset in the same pull
request. The ruleset's bypass list can still merge past a red check; nobody
merges into `main` while a required check is red. When editing the ruleset, also
restrict `main`'s allowed merge methods to `merge`: release pull requests must
keep the tagged commit in `main`'s history.

### Images

Each process has its own image, holding only what that process imports:

| Image | Dockerfile | Contents |
| --- | --- | --- |
| API (`ghcr.io/webtech-network/autograder-api`) | `Dockerfile.api` | `server` extra; `autograder`, `execution_host`, `sandbox_manager`, `web` |
| Sandbox manager | `Dockerfile.sandbox` | `sandbox` extra; `autograder`, `sandbox_manager` |
| Action (`ghcr.io/webtech-network/autograder-action`) | `Dockerfile.actions` | base dependencies and `git`; `autograder`, `execution_host`, `sandbox_manager`, `github_action` |
| Student runtimes | `sandbox_manager/images/` | see [LANGUAGES.md](../contracts/LANGUAGES.md#runtime-images) |

The three service and Action images share one layout: a digest-pinned
`python:3.13-slim` base, a build stage that installs only the locked runtime
dependencies (`uv sync --locked --no-dev`) into `/opt/venv`, and a final stage
with that environment and the first-party directories listed in its Dockerfile
under `/app` (`PYTHONPATH=/app`). There is no uv, Node.js, Docker CLI or daemon,
curl or test tool in them; the Docker SDK talks to a mounted socket. The build
context is an allow-list (`.dockerignore`): `.env` files, `.venv`, `data/`,
databases, `*.pem`/`*.key` files and caches never reach an image, even when they
sit inside an allowed directory. Any other file inside an allowed directory
(for example a stray `web/credentials.json`) does ship, so keep secrets out of
the source directories. To add a process or a file to an image, add its path to both the
allow-list and that image's `COPY` lines, and its expectation to
`tests/images/`.

`make test-images` builds the images and checks them against real Docker:
installed distributions (no pytest, web or database stack where the process does
not import one), absent executables (`dockerd`, `containerd`, `node`, `curl`...),
`/app` holding exactly the allow-list, a rebuild from a copy of the checkout with
planted `.env`, `.venv`, `data/`, keys and other secrets that must contain none of them,
and the Action image grading the static example the way a runner invokes it. CI
runs it on every pull request; `IMAGE_PREFIX` and `IMAGE_TAG` rename the local
images (`make test-images IMAGE_PREFIX=mine`).

To change a base, replace its digest (`docker buildx imagetools inspect
python:3.13-slim-trixie`) in all three Dockerfiles. The Action image is released
from the branch that raises its version in `action.yml`, before that branch
merges; see [Releasing a version](../github_action/README.md#releasing-a-version).

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

# Database (a disposable one; the compose stack's database is not published)
docker run -d --rm --name autograder-dev-postgres -p 127.0.0.1:5432:5432 \
  -e POSTGRES_USER=autograder -e POSTGRES_PASSWORD=development-only -e POSTGRES_DB=autograder \
  postgres:17-alpine
export DATABASE_URL=postgresql+asyncpg://autograder:development-only@localhost:5432/autograder
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
and the control service (`python -m sandbox_manager`, the compose
`sandbox-manager`) refuse to start with `IsolationRuntimeError`. For
`make start-autograder` (plain `docker compose up`, which reads
`docker-compose.override.yml`), give `sandbox-manager` the copy in that override:
mount `./sandbox_config.dev.yml:/config/sandbox.yml:ro` and set
`SANDBOX_CONFIG_FILE: /config/sandbox.yml`. `make test-http` names its compose
files explicitly, so no override applies: it tests the shipped images with
their own `runsc` configuration and needs `make gvisor-install`, as in CI.

Remote mode runs the private sandbox control API as a separate single-worker
process and requires its shared token ([SANDBOX.md](../contracts/SANDBOX.md)):

```bash
export SANDBOX_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
python -m sandbox_manager &                 # 127.0.0.1:8001, one worker
SANDBOX_MODE=remote SANDBOX_API_URL=http://127.0.0.1:8001 uvicorn web.main:app --port 8000
```

Every variable either process reads is listed in the
[configuration reference](../operate/configuration.md); an invalid, incoherent or
retired one stops startup with a message naming it.

`make start-autograder` runs the development stack of `docker-compose.yml` (the
[supported topology](../operate/deployment.md) with throwaway credentials). Export
`SANDBOX_API_TOKEN` and `AUTOGRADER_INTEGRATION_TOKEN` first. It migrates the
database in the one-shot `migrate` service, creates the fixture bucket and
uploads `examples/fixtures/` in `storage-init`, then starts the sandbox manager on
the project network only and the API on `127.0.0.1:8000`
(`AUTOGRADER_HTTP_PORT`; empty picks a free port). API docs are served at
http://localhost:8000/docs. Another stack runs beside it under another project
name: `docker compose -p <name> up -d --wait`. `docker compose down -v` deletes
a stack's data.

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
docker compose exec postgres psql -U autograder    # the compose stack's database
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
  references. The API and sandbox manager never pull images; only the Action
  pulls the pinned image of the language it grades.
- **401 from the API**: set `AUTOGRADER_INTEGRATION_TOKEN` and send
  `Authorization: Bearer <token>`.
- **Remote sandbox manager refuses to start**: set `SANDBOX_API_TOKEN` (or
  `SANDBOX_API_ALLOW_UNAUTHENTICATED=true` for local development only).
