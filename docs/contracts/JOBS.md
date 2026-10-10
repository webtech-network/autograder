# Durable HTTP work and host operations

`POST /api/v1/submissions` returns **202 Accepted**, with a `Location` header
pointing to `/api/v1/submissions/{id}`, only after PostgreSQL commits the accepted
input. Polling stays compact. Authenticated `/details` includes the saved source
objects, locale, scope, definition snapshot and finalized outcome.

The acceptance transaction saves the canonical definition/hash/revision, selected
language, locale, scope, files and host audit metadata. Later configuration edits
or deactivation do not change accepted work. Caller retry keys remain separate
work under #366: repeating a successful POST creates another submission.

## Ownership

`web.main.create_app` constructs one `WebHost`. Each app owns its settings,
session factory, provider resource owner and bounded worker set. Tests can inject
`session_factory`, `capabilities`, `resource_owner` and `evaluator`; they do not
replace module-global engines, resource managers or task sets. Settings are read
once when the host is constructed, without loading dotenv during startup.

Routes translate HTTP envelopes and errors. The concrete operations in
`web.service.submission_operations` accept work, ingest an authenticated
attestation and query/project stored submissions. Acceptance and attestation
operations commit once and roll back their own failures. Session contexts only
close and roll back unfinished transactions. Repositories flush, never commit.
`web.service.grading_service` evaluates saved input without importing a database.
`web.service.outcome_delivery` retains and publishes finalized outcomes, without
importing the grading runner. The engine knows nothing about jobs or leases.

## Worker policy

The API lifespan starts `WEB_WORKER_COUNT` workers (default **2 per process**).
Each worker claims at most one job at a time with PostgreSQL
`SELECT ... FOR UPDATE SKIP LOCKED`, commits an attempt UUID and a lease, then
runs outside the claim transaction. Internal attempt history is separate from
public `pending`, `processing`, `completed` and `failed` submission status.

A lease lasts `WEB_LEASE_SECONDS` (**60 seconds**) and renews every third of that
interval. Restarted workers reclaim expired `processing` work. Each new claim
changes the attempt UUID; publication locks the submission and requires the same
UUID. An old worker may finish cleanup, but cannot overwrite a newer attempt's
chosen outcome. An expired lease permits reclaim; the UUID remains authoritative
until another claim replaces it. Database clock time controls claim eligibility.

`WEB_MAX_ATTEMPTS` defaults to **3**. This budget covers interrupted attempts,
not ordinary assessed failures or failed student criteria. On exhaustion the host
stores a terminal `RECOVERY_EXHAUSTED` failure with null score/tree. An engine
failure already represented by a finalized outcome is published as that outcome.
`WEB_POLL_SECONDS` defaults to **1 second**. Database outages delay claims and
lease renewal; accepted rows remain durable.

Before database publication, the host fsyncs a private outcome receipt in
`WEB_OUTCOME_RECEIPT_DIR` (default `data/unpublished-outcomes`). A recovered claim
checks for its attempt's retained outcome before starting another attempt.
Commit acknowledgement ambiguity is resolved by comparing the existing outcome;
identical replay succeeds. Stale-attempt receipts cannot publish. Invalid receipts
are renamed `.invalid` for investigation and the normal bounded recovery policy
applies. Mount the receipt directory persistently and share it between replicas
that may recover each other's jobs. Publication failure cannot rewrite a completed
grade into an execution failure.

Shutdown stops new claims and drains existing evaluation threads, keeping leases
and provider ownership until grading/publication completes. It does not cancel
threads or close their providers underneath them. Cancellation of the async worker
wrapper likewise drains its evaluation and publishes before releasing ownership.
A process killed forcibly can leave an attempt running in external infrastructure;
a new attempt may begin after lease expiry. UUID fencing prevents competing
authoritative publications; sandbox cleanup belongs to the owning execution
session. Graceful shutdown can wait for a blocked external provider; configure
the deployment termination grace period accordingly.

Readiness checks PostgreSQL and host startup, so a sandbox or AI provider outage
does not prevent durable acceptance. Execution providers are acquired only when
selected tests need them. Readiness is not a guarantee that every provider is
currently available.

## Deployment and migration

Run the existing API command; its lifespan owns worker startup and recovery:

```sh
alembic -c web/alembic.ini upgrade head
uvicorn web.main:app --host 0.0.0.0 --port 8000
```

Set `DATABASE_URL`, `AUTOGRADER_INTEGRATION_TOKEN`, the required sandbox/provider
configuration, and a persistent `WEB_OUTCOME_RECEIPT_DIR`. Worker settings listed
above are positive values validated during construction. Multiple API processes
have independent workers and coordinate claims through the same PostgreSQL rows.
No separate queue product or scheduler service is required.

Migration **006** adds locale/scope, attempt identity/count, lease timestamps and
`grading_attempts`. Pre-migration pending/processing rows did not retain complete
scope/locale input. The migration marks them failed rather than fabricating that
input; their compact response reports `RECOVERY_INPUT_UNAVAILABLE` and null grade.
Historical completed artifacts remain unchanged. Stop old API processes before
migrating; an older process must not publish work after the new worker policy starts.

Explicit delivery replay uses the configured database and does not evaluate again:

```sh
python -m web.service.outcome_delivery data/unpublished-outcomes/submission-123-ABC.json
```

An invalid/stale receipt is an operational error. Keep it for investigation;
retrying an API request is a different operation from replaying a finalized grade.

## Verification and capacity boundary

`tests/web/test_durable_workers.py` uses real PostgreSQL through
`TEST_POSTGRES_URL`, creates a private schema for every test, and verifies
concurrent claims, lease recovery, stale publications, retry exhaustion, saved
receipt replay, transaction rollback and cancellation with a real worker thread.
SQLite tests cover HTTP projections and isolated operation behavior, not
PostgreSQL locking guarantees.

A local PostgreSQL 17 run on x86_64 with 12 logical CPUs acknowledged **200
concurrent requests in 0.622 seconds**. Each request contained one tiny Python
source file, using one shared small definition. Workers were disabled so this
measures durable acceptance independently from sandbox/AI execution; it is not
an execution throughput or production capacity promise. The regression repeats
the 200-request burst without a timing gate and records elapsed time and hardware.
