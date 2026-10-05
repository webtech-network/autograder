# Autograder HTTP adapter

The adapter accepts source files, binds a validated grading definition, runs the
shared engine, and persists its finalized terminal outcome. Definitions and
outcomes follow the [v1 decision record](../docs/contracts/DECISIONS.md). This is a
breaking wire/storage migration; legacy dictionaries are not accepted by live
endpoints.
The [executable contract guide](../docs/contracts/CONFORMANCE.md) contains a
validate/create/submit/poll smoke test and the generated OpenAPI reference.

## Operation

Configure `DATABASE_URL` and `AUTOGRADER_INTEGRATION_TOKEN`, install the repository
requirements, and start the server with `uvicorn web.main:app`. The existing
sandbox/provider deployment settings still apply. The integration token protects
internal-ID definition fetch, external outcome ingestion, and detailed submission
retrieval. Full HTTP identity/access control remains a separate work item (#318).

For an existing installation, back up the database and run the migration before
starting the new service:

```sh
cd web
alembic upgrade head
```

Migration `005` converts unambiguous valid configurations to the canonical
normalized definition/hash. Invalid configurations become inactive, with their
old input and validation evidence retained under `migration_error`; instructors
must provide a valid replacement before reactivation. Old definition columns are
removed. This migration is irreversible; restore the backup to roll it back.
Historical submissions are **unverified**, with no manufactured current-version
snapshot. Historical failed scores become null. The migration does not claim
that previous scores were recomputed or validated against the new contract.

## Configuration resources

- `POST /api/v1/configs/validate`: canonical definition body; pure validation,
  normalization and hash response without storage or provider calls.
- `POST /api/v1/configs`: `{ "external_assignment_id": "assignment", "definition": ... }`.
- `GET /api/v1/configs/{external_assignment_id}` and authenticated
  `GET /api/v1/configs/id/{id}` return the same resource, including inactive rows.
- `GET /api/v1/configs?limit=100&offset=0` lists active resources in ID order.
- `PATCH /api/v1/configs/{id}` or its `/external/{external_assignment_id}` alias
  accepts `definition` and/or `is_active`. These aliases share one implementation.

Use the quoted revision ETag returned by fetch/create as the PATCH `If-Match`
header, for example `If-Match: "1"`. Missing preconditions return 428, malformed
ones 422, and stale ones 412. Omitted fields retain their values; explicit null
is rejected. Changes, including activation, advance `version`; identical patches
are no-ops. The definition hash covers normalized grading semantics only.
Creating an existing alias, including an inactive one, returns 409. Reactivate
that resource instead of recreating it.

## Submission acceptance and reads

`POST /api/v1/submissions` accepts external assignment/user identity, username,
files, optional language/locale/metadata and optional evaluation scope. It binds
and stores the exact normalized definition, hash, and revision before scheduling
work. A single definition language is inferred; multiple languages require an
explicit allowed choice. Inactive/quarantined configurations reject new work;
already bound work remains tied to its accepted snapshot.

`GET /api/v1/submissions/{id}` is compact polling: identity, status, language,
UTC timestamps with offsets, authoritative nullable score, duration, provenance,
safe error and enrichment statuses. It excludes source files and the result tree.
`GET /api/v1/submissions` provides the same projection with combinable
`external_user_id`, `grading_config_id`, and `status` filters. History orders by
submission time descending, then ID descending. `limit` is 1–100; `offset` is
nonnegative. `/user/{external_user_id}` is the user-filtered alias.

Authenticated `GET /api/v1/submissions/{id}/details` additionally returns source
files, metadata, the bound definition snapshot, the complete canonical outcome,
and optional internal diagnostics. A completed zero score is an assessed grade;
a failed execution has null score/tree and a structured error. Legacy history
has `provenance_status: "unverified_legacy"`; new accepted/imported snapshots use
`"bound_snapshot"`, which records binding rather than proof of execution origin.
The old arbitrary `baseline_result_tree` submission input is removed.

Authenticated `POST /api/v1/submissions/external-results` accepts
`grading_config_id`, external user identity, username, language,
`definition_snapshot`, `outcome`, and optional `submission_metadata`. It validates
shared outcome invariants, hash/reference/revision/language, and complete result
placement, criterion IDs/evaluators and scoring ratios against the snapshot.
The current revision must match the stored hash. An older positive revision may
be attested by the authenticated host even after a configuration edit/deactivation;
this is trusted historical attestation, not server proof of a past definition.

422 validation errors expose `code`, `path`, and `message` without echoing rejected
source/payloads. Structural model paths begin with `body`; compilation paths are
relative to the definition. OpenAPI exposes the shared typed definition and
status-discriminated outcome models.

## Retaining and replaying finalized outcomes

Before database publication, HTTP writes the exact finalized outcome and its
submission ID to a private atomic receipt. Set `WEB_OUTCOME_RECEIPT_DIR` to a
persistent mounted directory; the default is `data/unpublished-outcomes` relative
to the service working directory. Receipts are mode 0600 and contain private
result data. The adapter fsyncs the file and directory before publication.
Successful publication removes the receipt. Database failure logs its path and
retains the completed/failed engine outcome unchanged; it never converts a
completed grade into a new failed grade.

After restoring database availability, replay a retained receipt explicitly:

```sh
python -m web.service.outcome_delivery /persistent/unpublished-outcomes/submission-42-0123456789abcdef.json
```

Replay validates provenance against the already bound submission and persists the
same execution without running the grader. If an identical result already exists
(for example after an uncertain commit acknowledgement), replay removes the
receipt safely; a conflicting existing result is rejected and the receipt remains.
A failed replay preserves the receipt for another attempt.

This receipt mechanism covers finalized-result publication. It does **not** make
pending/running task dispatch restart-safe, provide an automatic retry scheduler,
or demonstrate the 150–200-request capacity target. Durable acceptance and
recovery remain #365; submission/import replay identity remains #366. Deployments
must mount the receipt directory persistently to retain artifacts across container
replacement. Deliberate execution at `/api/v1/execute` remains supported separately.
