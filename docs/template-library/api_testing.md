# API Testing Template (`api`)

The API Testing template validates student-built web APIs by making HTTP requests to a running server inside a sandbox container and checking the responses.

!!! warning "Not available on the shipped hosts"
    API criteria need the `http_network` capability. The HTTP API and the GitHub
    Action do not provide it, so a definition using them fails with
    `SERVER_CAPABILITY_UNAVAILABLE` before any sandbox is acquired (see
    [How it works](#how-it-works)).

Parameters, defaults, constraints and capabilities of every evaluator below are in the generated [evaluator reference](../reference/evaluators.md#api); this page explains what the checks mean.

> **Template name for configs:** `api`  
> **Requires:** a host-supplied server session (`ServerSession.make_request()`)

---

## Test Functions

### `health_check`

Sends a GET request to an endpoint and verifies it returns HTTP status 200.

**Scoring:** 100 if status code is 200, 0 otherwise.

**Example:**
```json
{
  "id": "health-check",
  "type": "health_check",
  "name": "Health check",
  "parameters": {
    "endpoint": "/health"
  },
  "weight": 100
}
```

---

### `check_response_json`

Sends a GET request to an endpoint and verifies the JSON response contains a specific key-value pair.

**Scoring:** 100 if the response is valid JSON and contains the expected key-value pair, 0 otherwise.

**Example:**
```json
{
  "id": "check-response-json",
  "type": "check_response_json",
  "name": "Check response json",
  "parameters": {
    "endpoint": "/api/info",
    "expected_key": "version",
    "expected_value": "1.0"
  },
  "weight": 100
}
```

---

## Usage Example

A complete, schema-checked definition is [`docs/contracts/v1/examples/api.json`](../contracts/v1/examples/api.json). Over HTTP, send the definition as `definition` in the configuration envelope (`POST /api/v1/configs`, see [API.md](../API.md)). A snippet above is one criterion; [DEFINITIONS.md](../contracts/DEFINITIONS.md) describes the whole object.

## How It Works

API criteria declare the `http_network` capability. The host must supply a
`server_execution` capability (`ServerSession`) that starts the submission's
server after staging and setup, waits until it is reachable, sends each request
and stops the server when the run closes. Transport failures are execution
failures, not student zeros; an HTTP error status is an ordinary assessment.

**Current support:** the shipped Docker host supplies no server lifecycle, so an
API definition fails with `SERVER_CAPABILITY_UNAVAILABLE` before any sandbox is
acquired. See [CAPABILITIES.md](../contracts/CAPABILITIES.md).
