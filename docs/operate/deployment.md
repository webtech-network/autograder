# Deploying the HTTP service

One supported shape for the HTTP service, the state it keeps, and how to
upgrade it. Every variable named here is in the
[configuration reference](configuration.md). The GitHub Action has no
deployment: it runs on the workflow's runner ([trust](../github_action/trust.md)).

## Supported topology

One Docker host runs:

| Service | Image | Role |
| --- | --- | --- |
| `api` | `autograder-api` | Accepts and grades submissions. `SANDBOX_MODE=remote`; no Docker socket. The only published port (8000), behind your TLS proxy. |
| `sandbox-manager` | `autograder-sandbox-manager` | The private sandbox control API: the only service with the Docker socket. Exactly one replica, one worker, `expose` only (never `ports`), bearer token `SANDBOX_API_TOKEN` shared with `api`, and a fixed `hostname` unique on the Docker host. |
| PostgreSQL 17 | `postgres:17` | Durable submissions, outcomes and configurations ([Durable jobs](../contracts/JOBS.md)). |
| Fixture store (optional) | S3 or compatible | `EXTERNAL_ASSETS_BUCKET_NAME`. |

The runtime images named under `runtimes:` in `sandbox_config.yml` must be
pulled on the Docker host before `sandbox-manager` starts, and the Docker daemon
must offer the OCI runtime named by `general.runtime`: the shipped file says
`runsc` (gVisor), so check that `docker info` lists `runsc`, or deploy a
configuration with `runtime: runc` deliberately. Otherwise the manager refuses
to start ([environments and runtimes](../contracts/SANDBOX.md#environments-and-supported-topology)). How sandboxes are
isolated and bounded, and why only the manager holds the socket, is
[Sandbox ownership](../contracts/SANDBOX.md).

The repository's `docker-compose.yml` is this topology with development
settings (fixed throwaway credentials, an S3 emulator, a loopback port); start
from it, replacing the credentials with secrets and the emulator with your
store. `make test-http` proves it from the commit under test.

`SANDBOX_MODE=local` (the API's default) makes the API process own its
sandboxes through the Docker socket. It exists for development and tests: in a
deployment it puts root-equivalent Docker access in the internet-facing process.

## Persistent state

| State | Where | If it is lost |
| --- | --- | --- |
| Database | PostgreSQL volume | Everything: accepted work, outcomes, configurations. Back it up. |
| Outcome receipts | `WEB_OUTCOME_RECEIPT_DIR` on a volume (`/app/data/unpublished-outcomes` by default) | Grades finalized while the database was unreachable are graded again, or fail `RECOVERY_EXHAUSTED`. Share it between API replicas that may recover each other's jobs. |
| Sandbox containers | Docker daemon | Nothing: they are disposable. Each carries an owner lease; a restarted manager removes its dead predecessor's. |

The sandbox manager keeps handles in memory only. Restarting it ends in-flight
gradings, which are retried within `WEB_MAX_ATTEMPTS`.

## Upgrade runbook

The `deploy` job of `.github/workflows/verify.yml` runs steps 2 to 5 for the API
image of each verified commit on `main`. By hand:

1. **Read the migration notes** of the release: [retired variables](configuration.md#retired-variables),
   [Sandbox ownership](../contracts/DECISIONS.md#sandbox-ownership-and-configuration) and
   [Durable jobs](../contracts/JOBS.md#deployment-and-migration).
2. **Pull** the new `api` and `sandbox-manager` images and the runtime images of
   the new `sandbox_config.yml`.
3. **Check the configuration** with the new image; nothing is replaced if it fails:
   `docker compose run --rm --no-deps api python -m web.main --check`
4. **Back up and migrate** the database with the new image:
   `docker compose run --rm --no-deps api alembic -c web/alembic.ini upgrade head`.
   The API refuses to serve a database at another revision.
5. **Replace** the services: `docker compose up -d --no-deps sandbox-manager api`.
   Upgrade the manager and its clients together.
6. **Confirm** `GET /api/v1/ready` answers 200.
7. **Reclaim** sandboxes no manager can prove dead, which startup leaves alone:
   containers from before owner labels, or of a previous manager hostname (for
   example after leaving local mode, the API container's hostname):

   ```bash
   docker compose exec sandbox-manager python -m sandbox_manager.reclaim             # list with owners and status
   docker compose exec sandbox-manager python -m sandbox_manager.reclaim --legacy
   docker compose exec sandbox-manager python -m sandbox_manager.reclaim --dead-host <old-hostname>
   ```

   The command refuses containers whose owner is alive on that host.

## Moving an API-only deployment to this topology

A deployment that runs only the API, in local mode with the Docker socket:

1. Remove every [retired variable](configuration.md#retired-variables) from the
   API's environment (`CRITERIA_ASSETS_BUCKET_NAME` becomes
   `EXTERNAL_ASSETS_BUCKET_NAME`). The new image refuses to start while one is set.
2. Keep `WEB_OUTCOME_RECEIPT_DIR` on a volume.
3. Add the `sandbox-manager` service as in `docker-compose.yml`, with its own
   stable `hostname` and `SANDBOX_API_TOKEN`. Set `SANDBOX_MODE=remote`,
   `SANDBOX_API_URL=http://sandbox-manager:8001` and the token on `api`, and remove
   the Docker socket from `api`.
4. After the switch, reclaim the API's old sandboxes with
   `--dead-host <old API container hostname>` (step 7 above).
