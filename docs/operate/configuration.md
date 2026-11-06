# Configuration reference

Every environment variable a host reads, by host. Each host reads its settings
once, when it starts, and refuses to start on invalid, incoherent or retired
configuration with a message naming the variable. Nothing loads `.env` files:
set variables in the service definition (Compose `environment:`) or the process
environment. `tests/unit/test_settings_contract.py` fails when code reads a
variable missing from this page, or this page lists one that code does not read.

Sandbox pools and the host sandbox budget are not environment variables: they
live in the YAML file named by `SANDBOX_CONFIG_FILE`
(see [Sandbox ownership](../contracts/SANDBOX.md#one-host-wide-sandbox-budget)).
Optional providers stay lazy: the fixture store and the AI provider are first
contacted by the first grading that needs them
([Host capabilities](../contracts/CAPABILITIES.md)).

Check a configuration without starting the service, exactly as startup validates
it (no database, Docker or network access):

```bash
docker compose run --rm --no-deps api python -m web.main --check
```

## API service

`web.core.config.Settings` plus the execution providers it composes. Variables
marked *required* have no working default for a deployment.

| Variable | Default | Meaning |
| --- | --- | --- |
| `DATABASE_URL` | local development URL | *Required.* SQLAlchemy async URL of the PostgreSQL database, also used by `alembic` and `python -m web.database.schema`. |
| `DATABASE_ECHO` | `false` | Log every SQL statement (`true`/`false`). |
| `DATABASE_POOL_SIZE` | `10` | Connections kept per API process. |
| `DATABASE_MAX_OVERFLOW` | `20` | Extra connections beyond the pool (may be `0`). |
| `DATABASE_POOL_TIMEOUT` | `30` | Seconds to wait for a pooled connection. |
| `DATABASE_POOL_RECYCLE` | `3600` | Seconds before a connection is replaced. |
| `AUTOGRADER_INTEGRATION_TOKEN` | empty | *Required.* Bearer token of the integration principal. Unset, protected routes answer 503 and `/ready` reports not ready ([AUTH.md](../contracts/AUTH.md)). |
| `AUTOGRADER_ATTESTATION_TOKENS` | empty | `name=token,...` producer credentials limited to publishing external results. |
| `WEB_OUTCOME_RECEIPT_DIR` | `data/unpublished-outcomes` | *Persistent.* Directory of finalized outcomes not yet published to the database; relative to the working directory (`/app` in the image). Mount it on a volume ([Durable jobs](../contracts/JOBS.md)). |
| `WEB_WORKER_COUNT` | `2` | Grading workers per API process. |
| `WEB_LEASE_SECONDS` | `60` | Lease of a claimed job; renewed every third. |
| `WEB_MAX_ATTEMPTS` | `3` | Interrupted attempts before `RECOVERY_EXHAUSTED`. |
| `WEB_POLL_SECONDS` | `1` | Idle worker polling interval. |
| `SANDBOX_MODE` | `local` | `local`: the API process owns its sandboxes through the Docker socket (development and tests). `remote`: sandboxes come from the private sandbox manager (the supported deployment, see [Deployment](deployment.md)). |
| `SANDBOX_API_URL` | `http://localhost:8001` | Sandbox manager URL (`remote`). |
| `SANDBOX_API_TOKEN` | empty | Sandbox manager bearer token (`remote`); the same value as the manager's. |
| `SANDBOX_CONFIG_FILE` | `sandbox_config.yml` | Sandbox budget, pools and runtime images (`local`); relative paths resolve from the project root. Read when the first sandbox is acquired. |
| `EXTERNAL_ASSETS_BUCKET_NAME` | unset | S3 bucket holding definition fixtures. Unset, the host has no fixture store and fixture assignments fail preparation. |
| `S3_ENDPOINT_URL` | AWS | S3-compatible endpoint. Setting it without a bucket stops startup. |
| `AWS_REGION` | `us-east-1` | Region of the fixture bucket and of the AI secret. |
| `AWS_ACCESS_KEY_ID` | SDK default chain | Fixture store credential; set together with the secret key or neither. |
| `AWS_SECRET_ACCESS_KEY` | SDK default chain | Fixture store credential. |
| `OPENAI_API_KEY` | unset | Key of the AI assessment provider. |
| `AUTOGRADER_AI_MODEL` | `o4-mini-2025-04-16` | AI assessment model. |
| `ENVIRONMENT` | unset | `production` reads the AI key from AWS Secrets Manager when `OPENAI_API_KEY` is unset. |
| `AUTOGRADER_AI_SECRET_NAME` | `AUTOGRADER_OPENAI_KEY` | Secrets Manager entry (`ENVIRONMENT=production`). |
| `JSON_LOGS` | `false` | JSON log lines (`true` in production). |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` or `CRITICAL`. |
| `SERVICE_NAME` | `autograder-api` | `service` field of log lines. |
| `APP_ENV` | `local` | `env` field of log lines. |

Booleans accept `true`/`false`, `1`/`0` and `yes`/`no`; anything else stops
startup, as do non-numeric numbers and out-of-range values.

## Sandbox manager

The private control API (`sandbox_manager.api.ControlSettings`), one per Docker
host ([Sandbox ownership](../contracts/SANDBOX.md#private-control-api)).

| Variable | Default | Meaning |
| --- | --- | --- |
| `SANDBOX_API_TOKEN` | unset | *Required.* Bearer token every client must send. |
| `SANDBOX_API_ALLOW_UNAUTHENTICATED` | `false` | Run without a token. Local development only. |
| `SANDBOX_CONFIG_FILE` | `sandbox_config.yml` | Sandbox budget, pools and runtime images. |
| `SANDBOX_HANDLE_TTL_SECONDS` | `600` | Idle time before a handle expires. |
| `SANDBOX_HANDLE_TOMBSTONE_SECONDS` | `3600` | How long closed handles are remembered. |
| `WEB_CONCURRENCY` | `1` | Must be `1`: handles live in process memory (Uvicorn also reads it). |
| `SANDBOX_HOST` | `127.0.0.1` | Bind address of `python -m sandbox_manager`. The image's command binds `0.0.0.0:8001`. |
| `SANDBOX_PORT` | `8001` | Port of `python -m sandbox_manager`. |

## GitHub Action

The Action is configured through its inputs
([configuration](../github_action/configuration.md)). The runner provides the
`GITHUB_*`/`RUNNER_*` variables; the others reach the Action only through a
workflow's `env:`.

| Variable | Default | Meaning |
| --- | --- | --- |
| `GITHUB_WORKSPACE` | `.` | Base of relative input paths. |
| `GITHUB_OUTPUT` | unset | Step outputs file. |
| `GITHUB_STEP_SUMMARY` | unset | Job summary file. |
| `GITHUB_ACTIONS` | unset | Must be `true` to publish. |
| `GITHUB_EVENT_NAME` | unset | Trusted-event check and provenance. |
| `GITHUB_EVENT_PATH` | unset | Event payload, for provenance. |
| `GITHUB_REPOSITORY` | unset | Default submitter name and provenance. |
| `GITHUB_REPOSITORY_ID` | unset | Default submitter ID and provenance. |
| `GITHUB_REF` | unset | Provenance. |
| `GITHUB_SHA` | unset | Provenance. |
| `GITHUB_RUN_ID` | unset | Provenance. |
| `GITHUB_RUN_ATTEMPT` | unset | Provenance. |
| `GITHUB_WORKFLOW_REF` | unset | Provenance. |
| `GITHUB_ACTOR` | unset | Provenance (never the submitter). |
| `GITHUB_TRIGGERING_ACTOR` | unset | Provenance. |
| `RUNNER_ENVIRONMENT` | unset | `github-hosted` unless `trusted-self-hosted-runner` is set ([trust](../github_action/trust.md)). |
| `SANDBOX_MODE` | `remote` | Execution host mode, as for the API. |
| `SANDBOX_API_URL` | `http://localhost:8001` | As for the API. |
| `SANDBOX_API_TOKEN` | unset | As for the API. |
| `SANDBOX_CONFIG_FILE` | `sandbox_config.yml` | As for the API. |
| `EXTERNAL_ASSETS_BUCKET_NAME` | unset | As for the API. |
| `S3_ENDPOINT_URL` | AWS | As for the API. |
| `AWS_REGION` | `us-east-1` | As for the API. |
| `AWS_ACCESS_KEY_ID` | SDK default chain | As for the API. |
| `AWS_SECRET_ACCESS_KEY` | SDK default chain | As for the API. |
| `OPENAI_API_KEY` | unset | As for the API. |
| `AUTOGRADER_AI_MODEL` | `o4-mini-2025-04-16` | As for the API. |
| `ENVIRONMENT` | unset | As for the API. |
| `AUTOGRADER_AI_SECRET_NAME` | `AUTOGRADER_OPENAI_KEY` | As for the API. |

## Retired variables

A host refuses to start while one of these is set to a non-empty value, and
names its replacement. Remove them from service definitions.

| Variable | Host | Replacement |
| --- | --- | --- |
| `SANDBOX_POOL_SIZE` | API | `general.max_sandboxes` (budget) and `general.pool_size` (warm containers) in `sandbox_config.yml`. |
| `API_HOST` | API | Never read: the image serves on `0.0.0.0:8000`; choose the published address in Compose `ports`. |
| `API_PORT` | API | As `API_HOST`. |
| `API_WORKERS` | API | One API process per container; scale grading with `WEB_WORKER_COUNT`. |
| `UPSTASH_REDIS_URL` | API | None: outcomes are stored in PostgreSQL. |
| `UPSTASH_REDIS_TOKEN` | API | None. |
| `CRITERIA_ASSETS_BUCKET_NAME` | API | `EXTERNAL_ASSETS_BUCKET_NAME`. |
| `AWS_ACCESS_ID` | API | `AWS_ACCESS_KEY_ID`. |
| `SANDBOX_MAX_HANDLES` | Sandbox manager | `general.max_sandboxes` bounds open handles. |
