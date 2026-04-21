# API Testing Template

**Registry key:** `api` · **Sandbox:** Required · **Languages:** Python, Java, Node.js, C++

The API testing template tests REST APIs running inside a sandbox container. The student's server is started via setup commands, and tests make HTTP requests to verify endpoints.

!!! info "How it works"
    The autograder starts the student's server inside a Docker container, waits for it to be ready, then sends HTTP requests to test endpoints. Tests communicate with the server via `localhost` inside the sandbox.

## Available Tests

| Test Name | Purpose |
|-----------|---------|
| [`health_check`](#health_check) | Verify an endpoint returns HTTP 200 |
| [`check_response_json`](#check_response_json) | Verify a JSON response contains a specific key-value pair |

---

## health_check

Sends a GET request to the specified endpoint and checks that the server responds with HTTP status 200.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `endpoint` | string | Yes | `""` | API endpoint path (e.g., `"/health"`, `"/api/status"`) |

### Scoring

- **100** if the response status code is 200
- **0** if the status code is anything else, or if the request fails

### Example

```json
{
  "name": "health_check",
  "parameters": [
    { "name": "endpoint", "value": "/health" }
  ]
}
```

---

## check_response_json

Sends a GET request to the specified endpoint and checks that the JSON response contains a specific key with a specific value.

### Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `endpoint` | string | Yes | `""` | API endpoint path |
| `expected_key` | string | Yes | `""` | JSON key to look for in the response |
| `expected_value` | any | No | `None` | Expected value for the key. If `None`, only checks that the key exists. |

### Scoring

- **100** if the response is HTTP 200, the body is valid JSON, and `response[expected_key] == expected_value`
- **0** if the status code is not 200, the body is not valid JSON, the key is missing, or the value doesn't match

### Example

```json
{
  "name": "check_response_json",
  "parameters": [
    { "name": "endpoint", "value": "/api/users/1" },
    { "name": "expected_key", "value": "name" },
    { "name": "expected_value", "value": "Alice" }
  ]
}
```

---

## Setup Requirements

API testing requires a `setup_config` to start the student's server before tests run. The setup commands are executed inside the sandbox container.

```json
{
  "external_assignment_id": "rest-api-assignment",
  "template_name": "api",
  "languages": ["python"],
  "setup_config": {
    "python": {
      "required_files": ["app.py", "requirements.txt"],
      "setup_commands": [
        "pip install -r requirements.txt",
        "python3 app.py &"
      ]
    }
  },
  "criteria_config": { ... }
}
```

!!! warning "Server startup"
    Make sure the last setup command starts the server in the background (with `&`). The server must be listening before tests begin.

---

## Complete Configuration Example

A REST API assignment testing health and user endpoints:

```json
{
  "base": {
    "weight": 100,
    "subjects": [
      {
        "subject_name": "Server Health",
        "weight": 20,
        "tests": [
          {
            "name": "health_check",
            "parameters": [
              { "name": "endpoint", "value": "/health" }
            ]
          }
        ]
      },
      {
        "subject_name": "User Endpoints",
        "weight": 80,
        "tests": [
          {
            "name": "check_response_json",
            "parameters": [
              { "name": "endpoint", "value": "/api/users/1" },
              { "name": "expected_key", "value": "id" },
              { "name": "expected_value", "value": 1 }
            ],
            "weight": 50
          },
          {
            "name": "check_response_json",
            "parameters": [
              { "name": "endpoint", "value": "/api/users/1" },
              { "name": "expected_key", "value": "name" },
              { "name": "expected_value", "value": "Alice" }
            ],
            "weight": 50
          }
        ]
      }
    ]
  }
}
```
