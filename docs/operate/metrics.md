# Metrics

Both services expose Prometheus metrics in the text format at `GET /metrics`:

| Service | Target | Content |
| --- | --- | --- |
| `api` (`autograder-api`) | `http://api:8000/metrics` | HTTP, grading pipeline, queue, database pool; sandbox pools in `SANDBOX_MODE=local` |
| `sandbox-manager` (`autograder-sandbox-manager`) | `http://sandbox-manager:8001/metrics` | HTTP of the control API, sandbox pools and budget |

`/metrics` needs no credential, like `/health`: it carries counts, durations and
closed-set labels only, never identifiers, paths, tokens, names or submission
content. Scrape it from the private network and never route it publicly: the
proxy in front of `api` forwards `/api/` only (see
[deployment](deployment.md#supported-topology)), and the sandbox manager's port
is never published at all (see
[SANDBOX.md](../contracts/SANDBOX.md#private-control-api)). It is not part of the
OpenAPI contract. Each service process keeps its own counters, which restart at
zero with the process; `rate()` and `increase()` handle that.

## Labels

Every label has a closed set of values, so the number of series is fixed by the
deployment, not by traffic:

| Label | Values |
| --- | --- |
| `method` | `GET`, `HEAD`, `POST`, `PUT`, `PATCH`, `DELETE`, `OPTIONS`, else `OTHER` |
| `route` | the matched route template (`/api/v1/submissions/{submission_id}`), or `unmatched` |
| `status` (HTTP) | the response status code; an unhandled exception is `500` |
| `language` | a [supported language](../contracts/LANGUAGES.md) |
| `status` (grading) | `completed` or `failed` |
| `error_category`, `category` | the [outcome error categories](../contracts/OUTCOMES.md), `none` on success |
| `code` | the published [outcome error codes](../contracts/OUTCOMES.md) |
| `state` | pool states, or queue states (below) |

A value outside its set is reported as `other` (grading labels) or `OTHER` (methods).

## HTTP (both services)

| Metric | Type | Labels |
| --- | --- | --- |
| `http_server_requests_total` | counter | `method`, `route`, `status` |
| `http_server_request_duration_seconds` | histogram (0.01–10 s) | `method`, `route` |
| `http_server_requests_in_progress` | gauge | `method` |

The `api` service's `POST /sandboxes/{language}` calls to the sandbox manager
appear on the sandbox manager's target, which gives the control-API latency.

## Grading pipeline (`api`)

| Metric | Type | Labels | Meaning |
| --- | --- | --- | --- |
| `autograder_submissions_total` | counter | `status`, `language`, `error_category` | Final outcomes finalized by this process's workers (published, or retained for delivery). External attestations are not gradings and are not counted. |
| `autograder_grading_failures_total` | counter | `category`, `code`, `retryable` | Every failed attempt, including ones released for a [retry](../contracts/JOBS.md#execution-retry). |
| `autograder_grading_duration_seconds` | histogram (0.5–600 s) | `language`, `status` | One attempt from claim to outcome, including the wait for a sandbox. |
| `autograder_grading_in_progress` | gauge | | Attempts this process runs now. |

## Queue (`api`)

The backlog is the shared database queue, read with one grouped query over the
open statuses each scrape (bounded by a 5 s timeout), so every replica reports
the same values; aggregate with `max`, not `sum`.

| Metric | Type | Meaning |
| --- | --- | --- |
| `autograder_queue_submissions{state}` | gauge | `pending` (accepted, never claimed), `processing` (an attempt owns it) and `retry_wait` (released after a retryable failure, waiting for its backoff) |
| `autograder_queue_oldest_age_seconds` | gauge | Age of the oldest pending submission; `0` when none, `NaN` when the query failed |
| `autograder_queue_up` | gauge | `1` if the last scrape read the queue; `0` if the query failed (the queue counts are then absent and a warning is logged) |

## Database pool (`api`)

Read from the SQLAlchemy pool at scrape time; a pool without a size (`NullPool`,
`StaticPool`) reports no gauges. Sized by `DATABASE_POOL_SIZE` and
`DATABASE_MAX_OVERFLOW` ([configuration](configuration.md)).

| Metric | Type | Meaning |
| --- | --- | --- |
| `autograder_db_pool_size` | gauge | Connections the pool keeps |
| `autograder_db_pool_checked_out` | gauge | Connections in use |
| `autograder_db_pool_checked_in` | gauge | Idle connections |
| `autograder_db_pool_overflow` | gauge | Connections open beyond the pool size |
| `autograder_db_pool_max_overflow` | gauge | Connections allowed beyond the pool size |
| `autograder_db_pool_connections_created_total` | counter | Connections opened |
| `autograder_db_pool_connect_duration_seconds` | histogram (5 ms–5 s) | Time to open one connection |

Saturation is `checked_out / (size + max_overflow)`; at 1, requests and workers
wait up to `DATABASE_POOL_TIMEOUT` for a connection.

## Sandboxes (`sandbox-manager`, or `api` in local mode)

| Metric | Type | Labels | Meaning |
| --- | --- | --- | --- |
| `autograder_sandboxes` | gauge | `language`, `state` | Containers per pool state: `idle` (warm), `creating`, `active`, `closing`, `quarantined` |
| `autograder_sandbox_pool_target` | gauge | `language` | Idle containers the pool keeps warm (`pool_size`) |
| `autograder_sandbox_budget_limit` | gauge | | `max_sandboxes` |
| `autograder_sandbox_budget_held` | gauge | | Budget slots held (every non-idle container) |
| `autograder_sandbox_budget_waiting` | gauge | | Acquisitions waiting for a slot |

Budget utilization is `held / limit`; `waiting > 0` means gradings queue for
sandbox capacity. A non-zero `quarantined` count needs the attention described in
[SANDBOX.md](../contracts/SANDBOX.md). A local-mode `api` reports these once its
manager started; a remote-mode `api` reports none (scrape the sandbox manager).

## Example scrape configuration

```yaml
scrape_configs:
  - job_name: autograder-api
    static_configs: [{targets: ["api:8000"]}]
  - job_name: autograder-sandbox-manager
    static_configs: [{targets: ["sandbox-manager:8001"]}]
```
