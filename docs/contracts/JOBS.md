# Durable HTTP work and host operations

`POST /api/v1/submissions` returns **202 Accepted**, with a `Location` header
pointing to `/api/v1/submissions/{id}`, only after PostgreSQL commits the accepted
input. Polling stays compact. Authenticated `/details` includes the saved source
objects, locale, scope, definition snapshot and finalized outcome.

The acceptance transaction saves the canonical definition/hash/revision, selected
language, locale, scope, files and host audit metadata. Later configuration edits
or deactivation do not change accepted work. A repeated POST with
the same `Idempotency-Key` returns the original submission; without a key every
POST is new work. See [replay-safe acceptance](REPLAY.md).

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

## Sandbox capacity

One number bounds execution on a host: the sandbox budget N,
`general.max_sandboxes` in `sandbox_config.yml`, read by whichever process owns
the sandbox manager (the API in local mode, the sandbox service in remote mode).
Grading and `POST /execute` of every language share it; see
[SANDBOX.md](SANDBOX.md#one-host-wide-sandbox-budget). Workers are not capacity:
`WEB_WORKER_COUNT` may exceed N (and several API processes may share one remote
sandbox service). A grading that finds every slot held waits for one while its
lease keeps renewing; it is never failed for capacity. The wait is bounded by
`GRADING_CAPACITY_WAIT_SECONDS` (600 s); expiry is a retryable
`CAPABILITY_UNAVAILABLE` with no score (re-queuing it is COR-03 (#418)). Sandbox
clocks start when the slot is granted. A deliberate run waits 10 s, then answers
`503 EXECUTION_BUSY` with `Retry-After: 5`.

**Sizing rule.** N is a CPU budget. Each sandbox may use 0.5 CPU and 128 MiB
(`docker_profile.py`); gVisor, Docker and the API need the rest of the machine.
Start with N ≈ 2/3 of the host's logical CPUs and raise it only while measured
throughput still rises (the PRF-07 (#439) benchmark): beyond the CPU knee a
larger N only adds latency. Memory must cover N × 128 MiB plus `pool_size` warm
containers per language. **Reference:** 12 logical CPUs, gVisor, PostgreSQL 17 →
**about 8**. In the investigation behind this budget (#435: 200 five-test Python
bursts on a shared machine) waiting plus creation outside the lock completed
181 / 199 / 198 gradings per minute with 8 / 16 / 24 workers and no failures,
against 106–114 per minute and up to 188 of 200 capacity failures before.

`tests/e2e/test_sandbox_budget.py` runs a real API process with PostgreSQL and
Docker, six workers and `max_sandboxes: 2`: every submission of a burst, mixed
with deliberate runs, completes; saturated deliberate runs answer
`EXECUTION_BUSY`; shutdown leaves no container of the API's owner lease.

## Deployment and migration

Migrations in `web/migrations` are the only owner of the database schema. Apply
them as a separate one-shot step with the new build, then start the API; its
lifespan owns worker startup and recovery:

```sh
alembic -c web/alembic.ini upgrade head     # uses DATABASE_URL
uvicorn web.main:app --host 0.0.0.0 --port 8000
```

Compose runs the same command in its `migrate` service before `api` starts, and
the deploy workflow runs it with the pulled image before replacing the running
API. Startup never creates or alters tables. It compares the database revision
with the build's head revision and refuses to start, naming the command to run,
when the database is empty, behind, ahead or unversioned. `tests/web/test_migrations.py`
proves on PostgreSQL that `upgrade head` from empty equals the models (an empty
autogenerate diff), so a model change without a migration fails CI.

Set `DATABASE_URL`, `AUTOGRADER_INTEGRATION_TOKEN`, the required sandbox/provider
configuration, and a persistent `WEB_OUTCOME_RECEIPT_DIR`. Worker settings listed
above are positive values validated during construction. Multiple API processes
have independent workers and coordinate claims through the same PostgreSQL rows.
No separate queue product or scheduler service is required.

### Existing databases

Back up the database and stop old API processes before migrating; an older
process must not publish work after a new worker policy starts.

- **At revision `007`**: `upgrade head` applies the remaining revisions. Revision
  `007` is the squashed baseline of the old `001`-`007` chain and reproduces its
  schema exactly. Revision `008` converts the naive configuration/submission
  timestamps to timezone-aware ones, reading stored values as UTC (the database
  `TimeZone` used by the supported images), and drops the `006` backfill defaults.
  Revision `009` excerpts stored outcome reports and feedback to the outcome text
  bounds ([OUTCOMES.md](OUTCOMES.md)).
- **At `001`-`006`**: first run `upgrade 007` with a release that still contains
  the old chain (commit `3a8abcc`), then `upgrade head` with this one. That chain
  includes the irreversible definition conversion `005`.
- **Created by an older API startup** (no `alembic_version` table): run
  `python -m web.database.schema adopt` with `DATABASE_URL` set. It stamps revision
  `008` (the schema the old startup created) only when the live schema equals the
  models, and otherwise prints the differences and changes nothing. Then run
  `upgrade head`, which applies the later data migrations such as `009`. Reconcile those differences, or, when
  `pg_dump --schema-only` matches `tests/web/fixtures/legacy_007_schema.sql` (the
  old chain's schema), run `alembic -c web/alembic.ini stamp 007` and upgrade.

Pre-`006` pending/processing rows did not retain complete scope/locale input; `006`
marked them failed rather than fabricating that input. Their compact response
reports `RECOVERY_INPUT_UNAVAILABLE` and a null grade, and historical completed
artifacts remain `unverified_legacy`. Both survive `upgrade head` unchanged.

Migration **010** binds stored data to the closed vocabularies: stored locales
become canonical (`pt_br` → `pt-br`; unsupported values, which the old translator
rendered in English, become `en`) and stored outcomes using the former HTTP code
`EXECUTION_FAILED` use `EXECUTION_ERROR`. It refuses to upgrade, listing result
IDs, if a stored outcome carries any other unpublished code. Drain retained
outcome receipts with the previous release before upgrading: a receipt holding
`EXECUTION_FAILED` no longer validates.

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
It runs in-process with workers disabled, so it does not measure HTTP serving,
grading throughput, sandbox capacity or acceptance latency under grading load;
the capacity benchmark below measures those.

## Capacity benchmark

`scripts/capacity_benchmark.py` measures an already running stack through its
public HTTP API with an integration token. It never starts, migrates or configures
the stack, so the same command works for the compose stack and a production-like
deployment. Against `docker compose up` (synthetic token `e2e-test-token`):

```sh
AUTOGRADER_INTEGRATION_TOKEN=e2e-test-token python scripts/capacity_benchmark.py \
  --url http://localhost:8000 --workload python-io \
  --api-pid "$(docker inspect -f '{{.State.Pid}}' autograder-api)" \
  --sandbox-label autograder.sandbox.owner_host=autograder-sandbox-manager > result.json
```

Each run fires one burst (`--submissions`, default 200) of concurrent submissions
and waits, by polling the run's history, until every accepted submission is
terminal. Workloads expand the checked-in v1 examples:

| `--workload` | Definition | Submission | Executes in |
| --- | --- | --- | --- |
| `python-io` | `python-io.json` with `--tests` (5) stdin/stdout tests | distinct correct `main.py` | one sandbox per grading |
| `webdev` | `webdev.json` with `--criteria` (30) `has_tag` checks | distinct correct page of `--page-kb` (20) KiB | the API process |
| `mix` | both, alternating, plus `--executions` (12) concurrent `POST /execute` | as above | shared sandbox pools |

JSON on stdout reports, per run: acceptance latency percentiles and status codes;
drain time (first acceptance to last `graded_at`) and completed gradings per
minute; failures by code and completed scores; queue wait (acceptance to outcome
`started_at`) and grading-duration percentiles; deliberate-execution statuses;
sandbox containers before, at peak and after the run; API resident memory
(`--api-pid`, including children); load average; and the client and Docker host
hardware. `--runs N` repeats the burst and adds min/median/max. A short summary
goes to stderr.

The exit status gates correctness, never timing: **0** when every submission was
accepted and terminated with no failure code outside `--allow-failure`; **1** when
a submission was rejected, did not terminate before `--timeout`, failed with an
unexpected code (for example `CAPABILITY_UNAVAILABLE` at saturation), or a
deliberate execution answered other than 200/429/503; **2** when the stack is not
ready or the benchmark configuration is rejected.

Re-running leaves nothing behind: configurations are upserted under the aliases
`capacity-benchmark-python-io` and `capacity-benchmark-webdev` and deactivated
afterwards; requests carry no `Idempotency-Key`, so no operation receipts are
stored; outcome receipts are deleted by the host on publication. Submissions stay
as durable history under `external_user_id` `capacity-benchmark-<run id>`.
Sandbox leftovers are the labelled containers above the pre-run count once
disposal settles (`--settle-timeout`). The first burst on a cold stack creates the
warm pools (`pool_size` per language), which then count as leftovers; read
leftovers from a warmed stack. On a shared Docker host, narrow `--sandbox-label`
to this stack's owner (`python -m sandbox_manager.reclaim` lists owners); the
default app label counts every Autograder sandbox on the daemon.

`tests/integration/test_capacity_benchmark.py` is the opt-in check: with
`TEST_POSTGRES_URL` and the sandbox images it starts uvicorn on a private
PostgreSQL database with local Docker sandboxes, runs 20-submission mixed bursts
through the command and asserts termination, failure codes and cleanup, never time.

### Reference result

Recorded 2026-11-04 at commit `3a8abcc` on an Intel Core i5-12400 (6 cores,
12 threads), 31 GiB RAM, Linux 7.2, Docker 29.9 with gVisor (`runsc`) sandboxes,
PostgreSQL 17 in a container, Python 3.13, one uvicorn process in local sandbox
mode, `WEB_WORKER_COUNT=2` and the shipped `sandbox_config.yml` (`pool_size` 1,
`scale_limit` 3). The machine was shared with other jobs (load average 4–10), and
another process removed sandbox containers during python-io run 3 and the mix run
(Docker `404 No such container` in the API log); treat these numbers as an example
of the report, not as capacity of dedicated hardware. Three runs, min / median / max:

| 200-submission burst | python-io, 5 tests | webdev, 30 criteria, 20 KiB |
| --- | --- | --- |
| Acceptance p95 | 1.08 / 1.24 / 1.32 s | 1.69 / 1.86 / 1.86 s |
| Drain | 159 / 210 / 235 s | 23.6 / 24.6 / 24.9 s |
| Completed gradings per minute | 51 / 57 / 73 | 482 / 488 / 509 |
| Queue wait p95 | 150 / 197 / 214 s | 20.9 / 21.5 / 21.8 s |
| Grading duration p50 | 1.45 / 1.73 / 1.80 s | 0.16 / 0.16 / 0.16 s |
| Peak sandboxes (5 idle warm + active) | 7 / 7 / 7 | 0 |
| Peak API RSS | 110 / 115 / 115 MB | 126 / 128 / 129 MB |
| Failures | 0, 0, 7 (5 `SANDBOX_ERROR` from the external removal, 2 `CAPABILITY_UNAVAILABLE`) | 0 |

The same command reports the capacity defect of PRF-01 (#435) at this commit:
`--workload mix` failed 15/200 submissions (7 `CAPABILITY_UNAVAILABLE`, 8
`SANDBOX_ERROR`) and answered 11 of 12 deliberate executions with 503; python-io
with `WEB_WORKER_COUNT=6` failed 183/200 with `CAPABILITY_UNAVAILABLE`. Both exit 1.
