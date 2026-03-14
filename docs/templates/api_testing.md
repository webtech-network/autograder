# API Testing Template (`api_testing`)

The API Testing template validates student-built web APIs by making HTTP requests to a running server inside a sandbox container and checking the responses.

> **Template name for configs:** `api_testing`  
> **Requires sandbox:** Yes  
> **Communication:** HTTP requests to the containerized application via `SandboxContainer.make_request()`

---

## Test Functions

### `health_check`

Sends a GET request to an endpoint and verifies it returns HTTP status 200.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `endpoint` | string | ✓ | The endpoint to test (e.g., `"/health"`, `"/api/status"`) |

**Scoring:** 100 if status code is 200, 0 otherwise.

**Example:**
```json
{
  "name": "health_check",
  "parameters": { "endpoint": "/health" },
  "weight": 100
}
```

---

### `check_response_json`

Sends a GET request to an endpoint and verifies the JSON response contains a specific key-value pair.

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `endpoint` | string | ✓ | The API endpoint to test |
| `expected_key` | string | ✓ | JSON key to check in the response |
| `expected_value` | any | ✓ | Expected value for that key |

**Scoring:** 100 if the response is valid JSON and contains the expected key-value pair, 0 otherwise.

**Example:**
```json
{
  "name": "check_response_json",
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

```json
{
  "external_assignment_id": "rest-api-assignment",
  "template_name": "api_testing",
  "languages": ["python", "node"],
  "setup_config": {
    "required_files": ["app.py"],
    "setup_commands": [
      { "name": "Install dependencies", "command": "pip install flask" },
      { "name": "Start server", "command": "python app.py &" }
    ]
  },
  "criteria_config": {
    "base": {
      "weight": 100,
      "subjects": [
        {
          "subject_name": "API Endpoints",
          "weight": 100,
          "tests": [
            {
              "name": "health_check",
              "parameters": { "endpoint": "/health" },
              "weight": 30
            },
            {
              "name": "check_response_json",
              "parameters": {
                "endpoint": "/api/data",
                "expected_key": "status",
                "expected_value": "ok"
              },
              "weight": 70
            }
          ]
        }
      ]
    }
  }
}
```

## How It Works

Unlike the Input/Output and Web Dev templates, the API Testing template communicates with student code over HTTP:

1. The sandbox starts the student's web server (via setup commands or the program itself)
2. The sandbox container exposes a port
3. Test functions send HTTP requests to `http://localhost:{port}{endpoint}`
4. Responses are validated against expected values

This means the student's submission must be a runnable web server that listens on the expected port.

