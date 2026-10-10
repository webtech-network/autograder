# HTTP API v1 integration contracts

Run `uvicorn web.main:app`; interactive OpenAPI is at `/docs`.
The grading definition and outcome each carry their own `schema_version: "1.0"`.
See [definition contract](contracts/DEFINITIONS.md), [outcomes](contracts/OUTCOMES.md)
and [Actions migration](github_action/configuration.md).
For runnable integration examples and generated OpenAPI, see
[contract conformance](contracts/CONFORMANCE.md).

## Configurations

`POST /api/v1/configs` with `{external_assignment_id, definition}`. The definition
is compiled before saving. `POST /api/v1/configs/validate` accepts just the definition
and returns normalized JSON/hash without saving or provisioning resources.
`GET /api/v1/configs/{external_assignment_id}` resolves the alias even when inactive;
authenticated `GET /api/v1/configs/id/{config_id}` uses canonical identity. Responses include
`id`, `definition`, `definition_hash`, `version`, `is_active`, UTC timestamps,
optional migration errors and quoted revision `ETag`.

`GET /api/v1/configs` lists active configurations, with `limit` 1–100 and
nonnegative `offset`.

`PATCH /api/v1/configs/{config_id}` or
`PATCH /api/v1/configs/external/{external_assignment_id}` with an entire `definition`
and/or `is_active`. Supply `If-Match: "<version>"`. Omitted fields are preserved;
explicit nulls are rejected. Updates validate the full definition and atomically
check revision. Missing precondition is 428; stale revision is 412; malformed
precondition/definition is 422. Identical updates are no-ops. Duplicate aliases
are 409; reactivate the existing resource. PUT is retired.

## Submissions and results

`POST /api/v1/submissions` accepts `external_assignment_id`, `external_user_id`,
`username`, `files:[{filename,content}]`, optional language/locale/metadata and
typed evaluation scope/file context. Filenames are unique normalized relative
paths. A single definition language is inferred; multiple choices require one.
Inactive/quarantined definitions reject new work with 409. Acceptance binds the
exact definition snapshot/hash/revision, locale, scope and files in the acceptance
transaction. HTTP 202 includes a `Location` polling URL after commit. Host workers
claim saved jobs and recover interrupted attempts; see [durable jobs](contracts/JOBS.md).
The [submission input contract](contracts/SUBMISSIONS.md) defines canonical paths,
UTF-8, limits, scope membership and metadata semantics.

`GET /api/v1/submissions/{submission_id}` returns compact polling status, nullable `final_score`,
`execution_time_ms`, provenance/status, structured error and enrichment statuses.
It excludes files, trees and snapshots. Authenticated `GET /api/v1/submissions/{submission_id}/details`
adds the full canonical `outcome`, definition snapshot, locale, scope,
files/metadata and protected diagnostics. `submission_files[name]` is an object
with `filename`, exact `content`, nullable `changed_lines` and `file_metadata`. `GET /api/v1/submissions` provides history filtered by user, configuration
and status, with `limit` 1–100 and nonnegative `offset`, newest timestamp then ID.
`GET /api/v1/submissions/user/{external_user_id}` is the user-filtered projection. Terminal poll/history
scores come from the same persisted outcome; failed execution never means grade0.

Authenticated `POST /api/v1/submissions/external-results` accepts `grading_config_id`,
`external_user_id`, `username`, `language`, `definition_snapshot`, canonical
`outcome` and optional `submission_metadata`. It checks hash/resource/revision,
language, tree identity/placement/weights and terminal invariants. Current revision
must match current definition; an older revision is a trusted host attestation,
not cryptographic proof of server execution. Known inactive configurations can
receive historical results. No private files are required in an attestation.

Configure `AUTOGRADER_INTEGRATION_TOKEN` for protected endpoints. Missing server
configuration gives 503; absent/incorrect bearer token gives 401. Configuration
mutation/ordinary submission routes retain their existing deployment access policy;
broader authentication changes are tracked separately.

## Discovery and operations

`GET /api/v1/templates` and `GET /api/v1/templates/{template_name}` expose registry evaluator identifiers
and typed `parameters_schema` generated from the same executable contracts.
The OpenAPI models also include validated `sample_parameters`, evaluator-specific
`required_capabilities` and known `supported_languages`; the list response's
`capabilities` map explains deployment limitations. Use `evaluators[].identifier`
in place of the removed `available_tests` list. See the
[catalog and Python contract](contracts/CATALOG.md) for migration details.
Definitions may use input_output, static_analysis, webdev and api. Valid API
parameters do not imply the selected host has API networking; unavailable host
capabilities produce structured failed outcomes.

`GET /api/v1/health` returns service health, version and a UTC timestamp.
`GET /api/v1/ready` returns readiness and a UTC timestamp, with status 503 when the host cannot durably accept work. Execution-provider
availability is reported separately and does not strand accepted jobs.

`POST /api/v1/execute` is the [bounded deliberate execution API](features/deliberate_code_execution.md).
It requires the integration Bearer token. `test_cases` supplies stdin lines;
the response separates stdout, stderr, exit status and process category. Invalid
input is 422, unavailable infrastructure is 503, and the response deadline is
504. The endpoint shares the sandbox pool with grading.

Grading publication retains a private local receipt on DB failure;
[receipt replay](contracts/OUTCOMES.md#publication-receipts) retries publication without running evaluators.
Bounded workers use persisted PostgreSQL jobs, lease identities and fenced
publication. Submission idempotency remains separate work; replaying a finalized
outcome does not regrade it.
