# Web host architecture and deployment

The web host accepts work, runs bounded workers and publishes finalized engine
outcomes. Grading semantics remain in `autograder/`; persistence, scheduling,
HTTP authentication and deployment settings remain in `web/`.

`create_app(settings, session_factory=..., capabilities=...)` constructs one
`WebHost`. Each host has its own settings, session factory, resource owner,
catalog and worker task set. Tests can inject isolated sessions and fake
capabilities directly. Settings are read at construction; imports do not load
credentials or replace mutable database configuration.

The demonstrated operations are concrete functions in
`web/service/submission_operations.py`: acceptance, attested ingestion, history
and detail queries. Routes translate HTTP concerns and delegate to these
operations. Acceptance binds the normalized definition/hash/revision and the
complete source, scope, locale and language input in one transaction. Its owner
commits before returning 202 with a polling `Location`.

`web/service/worker.py` claims persisted jobs using PostgreSQL row locks and
leases. Each attempt has its own identity and bounded retry budget. It calls
`web/service/grading_service.py` with saved input and explicit host capabilities;
the engine is unaware of worker leases, database IDs or dispatch policies.

`web/service/outcome_delivery.py` writes a finalized outcome receipt and publishes
it under the attempt's row lock. It owns its publication transaction, validates
provenance and rejects stale ownership. Publication and receipt replay do not
import the grading runner. Session contexts close unfinished work without an
implicit second commit policy. Repositories are small concrete data-access
helpers; there is no generic repository interface hierarchy.

The host stops claims and drains execution threads before disposing providers.
Cancelling an asyncio wrapper does not establish that its underlying thread has
stopped. See [durable jobs](../contracts/JOBS.md) for leases, interrupted work,
receipts, startup/shutdown and migration behavior.

## Deployment

Configure `DATABASE_URL` and `AUTOGRADER_INTEGRATION_TOKEN`, apply migrations from
`web/` with `alembic upgrade head`, then run `uvicorn web.main:app`. PostgreSQL is
the supported concurrent worker deployment; SQLite is for isolated operation and
HTTP contract tests. Production workers must share the configured receipt
storage and database. See the [capability profiles](../contracts/CAPABILITIES.md)
for local/remote Docker, fixture and provider configuration.

`WEB_WORKER_COUNT`, `WEB_LEASE_SECONDS`, `WEB_MAX_ATTEMPTS` and `WEB_POLL_SECONDS`
control the documented worker policy. Keep `WEB_OUTCOME_RECEIPT_DIR` on persistent
private storage. A dependency outage can delay execution while the database
continues accepting jobs. Readiness checks durable acceptance separately from
provider availability. It does not promise that every provider is currently
available or that hundreds of environments can execute simultaneously.

The [HTTP API](../API.md), [accepted source input](../contracts/SUBMISSIONS.md) and
[executable examples](../contracts/CONFORMANCE.md) define the public wire contract.
Deliberate execution remains a bounded authenticated synchronous operation; it
shares the host's execution provider and bypasses grading job persistence.
