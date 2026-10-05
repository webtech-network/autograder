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
process; this example does not test recovery across service restarts.

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

Cloud fetch retries transient errors. Result POST is one attempt; after an
uncertain delivery, inspect the cloud
submission before using `retry-delivery-path` on the saved artifact. A failed
grade still has an outcome artifact with null score. Delivery failure retains
both artifacts and never changes a completed grade into a failed grade.

## Trusted Python extension

Run `PYTHONPATH=. python -m examples.contracts.custom_evaluator` for a complete
local `TestFunction` and `Template` example. It compiles a v1 definition with
`templates={"trusted_text": TrustedTextTemplate()}`, grades an in-memory
submission, and prints the terminal outcome. Only a trusted Python caller can
inject executable evaluator code. JSON sent to HTTP or Actions cannot load a
Python class, and no plugin upload API is advertised. The example uses
`compile_definition` followed by `evaluate_submission`; injected instances survive
that boundary. See the [catalog and Python facade](CATALOG.md) for the supported
surface, typed discovery responses and remaining INT-14 host responsibilities.

## Supported environments and test scope

| Example | Required environment | Automated verification |
| --- | --- | --- |
| HTTP static round trip | HTTP service and database; no Docker/provider | FastAPI ASGI client, actual definition compilation and grading, isolated SQLite persistence and polling |
| Ordinary Action | GitHub runner with Docker; ordinary checkout | Action shell/CLI in a local process with the static evaluator |
| Cloud Action | GitHub runner with Docker, reachable HTTP service, integration bearer token | Action shell/CLI and cloud wire tests; saved payload also passes real HTTP ingestion and polling |
| Custom Python evaluator | Trusted local Python process with repository requirements | Actual pipeline run, passing and assessed zero-score cases |

These tests do not establish production PostgreSQL recovery, live provider
availability, or runner isolation properties. The contract version is `1.0`.

## HTTP client integration

An HTTP client creates a configuration with `external_assignment_id` and one
`definition`. It can validate the definition first at
`POST /api/v1/configs/validate` without saving it. For an accepted example,
wrap [static-conformance.json](v1/examples/static-conformance.json) as
`{"external_assignment_id":"assignment-1","definition":<file contents>}`.
Updates use PATCH with the quoted revision `ETag` in `If-Match`.

A submission sends `files:[{filename,content}]` and an allowed language.
Polling returns compact status, nullable `final_score`, provenance, and a
structured error. After terminal polling, fetch authenticated
`GET /api/v1/submissions/{id}/details` for the result tree, feedback, files,
and diagnostics. A completed zero is an assessed grade; a failed null score
means grading did not produce a grade.

For pre-submission program runs, use the
[deliberate execution contract](../features/deliberate_code_execution.md).
It defines stdin cases, process output, request limits, and service failures.
The [legacy definition converter](DEFINITIONS.md#legacy-definition-migration)
is an offline tool for deployments with older definition files.
