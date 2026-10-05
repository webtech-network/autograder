# Executable integration examples

The source of truth for HTTP requests and responses is the [generated OpenAPI
document](v1/openapi.json). The [definition](v1/grading-definition.schema.json)
and [terminal outcome](v1/terminal-outcome.schema.json) schemas are generated from
the same typed Python models. All three use contract version `1.0`; run
`PYTHONPATH=. python scripts/generate_contract_schemas.py --check` after changing
their models. CI runs this check and the conformance tests. Regenerate with the
same command without `--check` when a model intentionally changes.

## HTTP: validate, create, submit, poll

For a local HTTP service with its configured database, run
`uvicorn web.main:app`, then from a checkout of this repository run:

```sh
PYTHONPATH=. python -m examples.contracts.http_round_trip --base-url http://127.0.0.1:8000
```

This executable example sends the complete [static definition](v1/examples/static-conformance.json)
to `POST /api/v1/configs/validate`, creates it at `POST /api/v1/configs`, sends
`files` as a **list** to `POST /api/v1/submissions`, and polls
`GET /api/v1/submissions/{submission_id}` until `completed` or `failed`. It uses
a unique assignment alias per invocation and prints the compact poll response.
The ordinary create and poll routes currently follow the deployment's existing
access policy; authenticated details and external ingestion require
`AUTOGRADER_INTEGRATION_TOKEN`. The example's `check_project_structure` evaluator
uses no sandbox or provider, making it suitable for local smoke tests.

The response to create is HTTP 200. A terminal `completed` status with score
zero is a valid assessment. `failed` has a null score and structured error; the
example exits nonzero in that case. Bad definitions and invalid external
attestations return 422. A missing configuration returns 404. New submissions
against inactive definitions return 409. Accepted ordinary submissions run in
process; durable recovery and replay identity are tracked by #365 and #366.

## GitHub Actions: ordinary checkout and cloud publication

Copy the same [static definition](v1/examples/static-conformance.json)
to `.github/autograder/definition.json` in the repository being graded. The
[ordinary Action workflow](../github_action/quick-start.md) grades a checkout
and writes `.autograder/outcome.json`. The [cloud workflow](../github_action/external-mode.md)
fetches `GET /api/v1/configs/id/{config_id}` with a bearer token, runs the same
definition, and sends `POST /api/v1/submissions/external-results` only when
`upload-to-cloud: "true"` is set. The saved `.autograder/delivery.json` is the
exact request envelope; its `outcome` equals the saved outcome artifact and
validates as `ExternalResultCreate` at the HTTP seam.

Cloud fetch retries transient errors. Result POST is one attempt because #366
has not added deduplication; after an uncertain delivery, inspect the cloud
submission before using `retry-delivery-path` on the saved artifact. A failed
grade still has an outcome artifact with null score. Delivery failure retains
both artifacts and never changes a completed grade into a failed grade.

## Trusted Python extension

Run `PYTHONPATH=. python -m examples.contracts.custom_evaluator` for a complete
local `TestFunction` and `Template` example. It compiles a v1 definition with
`templates={"trusted_text": TrustedTextTemplate()}`, grades an in-memory
submission, and prints the terminal outcome. Only a trusted Python caller can
inject executable evaluator code. JSON sent to HTTP or Actions cannot load a
Python class, and no plugin upload API is advertised.

## Supported environments and test scope

| Example | Required environment | Automated verification |
| --- | --- | --- |
| HTTP static round trip | HTTP service and database; no Docker/provider | FastAPI ASGI client, actual definition compilation and grading, isolated SQLite persistence and polling |
| Ordinary Action | GitHub runner with Docker; ordinary checkout | Action shell/CLI in a local process with the static evaluator |
| Cloud Action | GitHub runner with Docker, reachable HTTP service, integration bearer token | Action shell/CLI and cloud wire tests; saved payload also passes real HTTP ingestion and polling |
| Custom Python evaluator | Trusted local Python process with repository requirements | Actual pipeline run, passing and assessed zero-score cases |

These tests do not establish production PostgreSQL recovery, live provider
availability, or runner isolation properties. Execution environment and
capacity changes belong to #365 and #376. The contract version remains `1.0`;
this PR adds generated reference material and executable verification, with no
new HTTP or Action wire fields.

## Prisma consumer migration

The current Prisma backend at commit
[`3e2c2ed`](https://github.com/webtech-network/api-grader-prisma/tree/3e2c2edce4e386908bd1f8f44d19d6be469ed48d)
still sends separate `template_name`, `criteria_config`, `setup_config`, and
`include_feedback` fields in
[`AutograderConfigPayload`](https://github.com/webtech-network/api-grader-prisma/blob/3e2c2edce4e386908bd1f8f44d19d6be469ed48d/src/main/java/com/autograder/application/autograder/dto/AutograderConfigPayload.java).
The v1 create envelope instead contains `external_assignment_id` and one
`definition`. Build that definition from the existing assignment data, validate
it at `/api/v1/configs/validate`, then create it at `/api/v1/configs`. For a
concrete accepted value, wrap [static-conformance.json](v1/examples/static-conformance.json)
as `{"external_assignment_id":"<assignment UUID>","definition":<file contents>}`.
Use the offline [legacy converter](DEFINITIONS.md#migration-and-issue-reconciliation) where the
old rubric is unambiguous. Update uses PATCH with the entire new definition and
the fetched quoted `ETag` in `If-Match`; Prisma currently uses PUT without that
precondition in
[`AutograderClient`](https://github.com/webtech-network/api-grader-prisma/blob/3e2c2edce4e386908bd1f8f44d19d6be469ed48d/src/main/java/com/autograder/infrastructure/client/AutograderClient.java).

Prisma's submission request already uses `files:[{filename,content}]` and an
explicit language, which match v1. Its
[`AutograderSubmissionResponse`](https://github.com/webtech-network/api-grader-prisma/blob/3e2c2edce4e386908bd1f8f44d19d6be469ed48d/src/main/java/com/autograder/application/autograder/dto/AutograderSubmissionResponse.java)
still reads `feedback`, `result_tree`, `focus`, `submission_files`, and
`pipeline_execution` from ordinary polling. V1 polling deliberately returns
compact status, nullable `final_score`, `provenance`, and structured `error`.
After terminal polling, fetch authenticated `/api/v1/submissions/{id}/details` for
`outcome.tree`, `outcome.feedback`, files, and diagnostics as needed. Treat a
failed null score differently from a completed zero. Prisma's deliberate
`/api/v1/execute` request/response records use `test_cases` and a `results`
list. The [execution contract](../features/deliberate_code_execution.md)
preserves these fields while adding process details, request bounds, and
distinct service failures. Its contract test exercises the Prisma-shaped
request over HTTP.

Coordinate the Prisma DTO/service migration before deploying the v1 HTTP
contract to that consumer. No Prisma code is changed by this repository's PR.
