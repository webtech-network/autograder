# API Documentation

The Autograder provides a FastAPI-based REST API for integration with learning management systems.

## Starting the API

```bash
# Development
uvicorn web.main:app --reload

# Production
docker-compose up
```

API documentation (Swagger UI) available at: `http://localhost:8000/docs`

---

## Endpoints Overview

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/configs` | Create a grading configuration |
| `GET` | `/api/v1/configs` | List all grading configurations |
| `GET` | `/api/v1/configs/{external_assignment_id}` | Get configuration by assignment ID |
| `PUT` | `/api/v1/configs/{config_id}` | Update a grading configuration |
| `PUT` | `/api/v1/configs/external/{external_assignment_id}` | Update a grading configuration by external assignment ID |
| `POST` | `/api/v1/submissions` | Submit code for grading |
| `GET` | `/api/v1/submissions/{submission_id}` | Get submission details and results |
| `GET` | `/api/v1/submissions/user/{external_user_id}` | List submissions by user |
| `POST` | `/api/v1/execute` | Execute code without grading (DCE) |
| `GET` | `/api/v1/templates` | List available grading templates |
| `GET` | `/api/v1/templates/{template_name}` | Get template details |
| `GET` | `/api/v1/health` | Health check |
| `GET` | `/api/v1/ready` | Readiness check |

---

## Grading Configurations

### Create Grading Configuration

```http
POST /api/v1/configs
Content-Type: application/json
```

**Request Body:**
```json
{
  "external_assignment_id": "assignment-42",
  "template_name": "input_output",
  "criteria_config": {
    "base": {
      "weight": 100,
      "subjects": [
        {
          "subject_name": "Functionality",
          "weight": 60,
          "tests": [
            {
              "name": "expect_output",
              "parameters": {
                "inputs": ["Alice"],
                "expected_output": "Hello, Alice!",
                "program_command": "python3 main.py"
              },
              "weight": 100
            }
          ]
        }
      ]
    }
  },
  "languages": ["python", "java"],
  "setup_config": {
    "required_files": ["main.py"],
    "setup_commands": []
  }
}
```

**Request Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `external_assignment_id` | string | ✓ | External assignment ID from your LMS/platform |
| `template_name` | string | ✓ | Template to use (`input_output`, `web_dev`, `api_testing`) |
| `criteria_config` | object | ✓ | Grading criteria tree configuration |
| `languages` | list[string] | ✓ | Supported languages: `python`, `java`, `node`, `cpp` |
| `setup_config` | object | ✗ | Setup configuration for preflight checks |

**Response (201 Created):**
```json
{
  "id": 1,
  "external_assignment_id": "assignment-42",
  "template_name": "input_output",
  "criteria_config": { ... },
  "languages": ["python", "java"],
  "setup_config": { ... },
  "version": 1,
  "created_at": "2026-02-16T10:00:00Z",
  "updated_at": "2026-02-16T10:00:00Z",
  "is_active": true
}
```

**Error (400):** Configuration for this assignment already exists.

### List Grading Configurations

```http
GET /api/v1/configs?limit=100&offset=0
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 100 | Maximum results to return |
| `offset` | int | 0 | Pagination offset |

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "external_assignment_id": "assignment-42",
    "template_name": "input_output",
    "criteria_config": { ... },
    "languages": ["python"],
    "setup_config": null,
    "version": 1,
    "created_at": "2026-02-16T10:00:00Z",
    "updated_at": "2026-02-16T10:00:00Z",
    "is_active": true
  }
]
```

### Get Grading Configuration

```http
GET /api/v1/configs/{external_assignment_id}
```

**Response (200 OK):**
```json
{
  "id": 1,
  "external_assignment_id": "assignment-42",
  "template_name": "input_output",
  "criteria_config": { ... },
  "languages": ["python", "java"],
  "setup_config": null,
  "version": 1,
  "created_at": "2026-02-16T10:00:00Z",
  "updated_at": "2026-02-16T10:00:00Z",
  "is_active": true
}
```

**Error (404):** Configuration not found.

### Update Grading Configuration

```http
PUT /api/v1/configs/{config_id}
Content-Type: application/json
```

**Request Body (all fields optional):**
```json
{
  "template_name": "web_dev",
  "criteria_config": { ... },
  "languages": ["python", "node"],
  "setup_config": { ... },
  "is_active": false
}
```

**Response (200 OK):** Returns the updated configuration object (same schema as create response).

**Error (404):** Configuration not found.

### Update Grading Configuration by External ID

```http
PUT /api/v1/configs/external/{external_assignment_id}
Content-Type: application/json
```

Use this endpoint when you only know the LMS-specific assignment identifier and need to update the associated grading configuration without looking up its internal database ID. It accepts the same payload as the standard update route and performs a partial update via `exclude_unset` behavior.

**Request Body (all fields optional):**
```json
{
  "template_name": "web_dev",
  "criteria_config": { ... },
  "languages": ["python", "node"],
  "setup_config": { ... },
  "is_active": false
}
```

**Response (200 OK):** Updated configuration object (same schema as the create response).

**Error (404):** Configuration not found for the supplied `external_assignment_id`.

---

## Submissions

### Submit for Grading

```http
POST /api/v1/submissions
Content-Type: application/json
```

**Request Body:**
```json
{
  "external_assignment_id": "assignment-42",
  "external_user_id": "user_001",
  "username": "student123",
  "files": [
    {
      "filename": "main.py",
      "content": "print('Hello World')"
    }
  ],
  "language": "python",
  "metadata": {
    "attempt": 1
  }
}
```

**Request Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `external_assignment_id` | string | ✓ | External assignment ID (must match an existing grading config) |
| `external_user_id` | string | ✓ | External user ID from your platform |
| `username` | string | ✓ | Username of the submitter |
| `files` | list[object] | ✓ | List of files with `filename` and `content` |
| `language` | string | ✗ | Language override (defaults to first language in config) |
| `metadata` | object | ✗ | Optional metadata to attach to the submission |

**Response (200 OK):**
```json
{
  "id": 1,
  "grading_config_id": 1,
  "external_user_id": "user_001",
  "username": "student123",
  "status": "pending",
  "submitted_at": "2026-02-16T10:05:00Z",
  "graded_at": null,
  "final_score": null,
  "feedback": null,
  "result_tree": null,
  "focus": null
}
```

> **Note:** Grading runs asynchronously in the background. Poll the submission endpoint to check for results.

**Errors:**
- `404`: Grading configuration for the given assignment not found
- `400`: Specified language is not supported for this assignment

### Get Submission Results

```http
GET /api/v1/submissions/{submission_id}
```

**Response (Success — grading completed):**
```json
{
  "id": 1,
  "grading_config_id": 1,
  "external_user_id": "user_001",
  "username": "student123",
  "status": "completed",
  "submitted_at": "2026-02-16T10:05:00Z",
  "graded_at": "2026-02-16T10:05:03Z",
  "final_score": 85.5,
  "feedback": "## Grade: 85.5/100\n\n### ✅ Base Tests...",
  "result_tree": {
    "final_score": 85.5,
    "root": {
      "base": { ... },
      "bonus": { ... },
      "penalty": { ... }
    }
  },
  "focus": {
    "high_impact": [ ... ],
    "medium_impact": [ ... ],
    "low_impact": [ ... ]
  },
  "submission_files": {
    "main.py": "print('Hello World')"
  },
  "submission_metadata": null,
  "pipeline_execution": {
    "status": "success",
    "failed_at_step": null,
    "total_steps_planned": 7,
    "steps_completed": 7,
    "execution_time_ms": 4521,
    "steps": [
      {
        "name": "LOAD_TEMPLATE",
        "status": "success",
        "message": "Template loaded successfully"
      },
      {
        "name": "BUILD_TREE",
        "status": "success",
        "message": "Criteria tree built successfully"
      },
      {
        "name": "PRE_FLIGHT",
        "status": "success",
        "message": "All preflight checks passed"
      },
      {
        "name": "GRADE",
        "status": "success",
        "message": "Grading completed: 85.5/100"
      },
      {
        "name": "FEEDBACK",
        "status": "success",
        "message": "Feedback generated"
      }
    ]
  }
}
```

**Response (Preflight Failure):**
```json
{
  "id": 2,
  "grading_config_id": 1,
  "external_user_id": "user_001",
  "username": "student123",
  "status": "failed",
  "submitted_at": "2026-02-16T10:05:00Z",
  "graded_at": null,
  "final_score": 0,
  "feedback": "## Preflight Check Failed\n\n### Setup Command Failed: Compile Calculator.java\n...",
  "result_tree": null,
  "focus": null,
  "submission_files": { ... },
  "submission_metadata": null,
  "pipeline_execution": {
    "status": "failed",
    "failed_at_step": "PRE_FLIGHT",
    "total_steps_planned": 7,
    "steps_completed": 3,
    "execution_time_ms": 1523,
    "steps": [
      {
        "name": "PRE_FLIGHT",
        "status": "fail",
        "message": "Setup command 'Compile Calculator.java' failed with exit code 1",
        "error_details": {
          "error_type": "setup_command_failed",
          "phase": "setup_commands",
          "command_name": "Compile Calculator.java",
          "failed_command": {
            "command": "javac Calculator.java",
            "exit_code": 1,
            "stderr": "Calculator.java:4: error: ';' expected..."
          }
        }
      }
    ]
  }
}
```

**Response Fields (Detail View):**

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Submission ID |
| `grading_config_id` | int | Associated grading configuration ID |
| `external_user_id` | string | External user identifier |
| `username` | string | Submitter's username |
| `status` | string | `pending`, `processing`, `completed`, or `failed` |
| `submitted_at` | datetime | Submission timestamp |
| `graded_at` | datetime\|null | Grading completion timestamp |
| `final_score` | float\|null | Final grade (0-100+, includes bonus) |
| `feedback` | string\|null | Human-readable feedback report |
| `result_tree` | object\|null | Detailed grading results (null if grading didn't run) |
| `focus` | object\|null | Focus analysis grouping failed tests by impact |
| `submission_files` | object | Submitted files as `{filename: content}` map |
| `submission_metadata` | object\|null | Optional metadata attached at submission time |
| `pipeline_execution` | object\|null | Pipeline execution details with step-by-step status |

**Error (404):** Submission not found.

### List User Submissions

```http
GET /api/v1/submissions/user/{external_user_id}?limit=100&offset=0
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | int | 100 | Maximum results to return |
| `offset` | int | 0 | Pagination offset |

**Response (200 OK):**
```json
[
  {
    "id": 1,
    "grading_config_id": 1,
    "external_user_id": "user_001",
    "username": "student123",
    "status": "completed",
    "submitted_at": "2026-02-16T10:05:00Z",
    "graded_at": "2026-02-16T10:05:03Z",
    "final_score": 85.5,
    "feedback": "...",
    "result_tree": { ... },
    "focus": null
  }
]
```

---

## Deliberate Code Execution (DCE)

Execute code in a sandbox **without grading**. This is a stateless feature designed for testing and debugging — no data is persisted.

> 📚 For complete DCE documentation with examples in all languages, see [Deliberate Code Execution](features/deliberate_code_execution.md).

### Execute Code

```http
POST /api/v1/execute
Content-Type: application/json
```

**Request Body:**
```json
{
  "language": "python",
  "submission_files": [
    {
      "filename": "main.py",
      "content": "name = input('Enter name: ')\nprint(f'Hello, {name}!')"
    }
  ],
  "program_command": "python main.py",
  "test_cases": [["Alice"], ["Bob"]]
}
```

**Request Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `language` | string | ✓ | Programming language: `python`, `java`, `node`, or `cpp` |
| `submission_files` | list[object] | ✓ | Files with `filename` and `content` |
| `program_command` | string | ✓ | Command to execute (e.g., `python main.py`) |
| `test_cases` | list[list[string]] | ✗ | Optional test cases. Each test case is a list of stdin inputs. If omitted, the program runs once with no input. |

**Response (200 OK):**
```json
{
  "results": [
    {
      "output": "Enter name: Hello, Alice!\n",
      "category": "success",
      "error_message": null,
      "execution_time": 0.123
    },
    {
      "output": "Enter name: Hello, Bob!\n",
      "category": "success",
      "error_message": null,
      "execution_time": 0.118
    }
  ]
}
```

**Response Fields:**

| Field | Type | Description |
|-------|------|-------------|
| `results` | list[object] | One result per test case (or one result if no test cases provided) |
| `results[].output` | string | Combined stdout/stderr output |
| `results[].category` | string | `success`, `runtime_error`, `compilation_error`, `timeout`, or `system_error` |
| `results[].error_message` | string\|null | Error details if execution failed |
| `results[].execution_time` | float | Execution time in seconds |

**Errors:**
- `400`: Unsupported language
- `500`: Internal server error during execution

**Example — Simple Python:**
```bash
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{
    "language": "python",
    "submission_files": [
      {"filename": "main.py", "content": "print(\"Hello, World!\")"}
    ],
    "program_command": "python main.py"
  }'
```

**Example — Java with Compilation:**
```bash
curl -X POST http://localhost:8000/api/v1/execute \
  -H "Content-Type: application/json" \
  -d '{
    "language": "java",
    "submission_files": [
      {
        "filename": "Main.java",
        "content": "public class Main { public static void main(String[] args) { System.out.println(\"Hello!\"); } }"
      }
    ],
    "program_command": "javac Main.java && java Main"
  }'
```

---

## Templates

### List Available Templates

```http
GET /api/v1/templates
```

**Response (200 OK):**
```json
{
  "templates": [
    {
      "name": "input_output",
      "description": "...",
      "test_functions": [ ... ]
    },
    {
      "name": "web_dev",
      "description": "...",
      "test_functions": [ ... ]
    }
  ]
}
```

**Error (503):** Template service not initialized.

### Get Template Details

```http
GET /api/v1/templates/{template_name}
```

**Response (200 OK):** Returns detailed information about the template including all available test functions and their parameters.

**Errors:**
- `404`: Template not found
- `503`: Template service not initialized

---

## Health & Readiness

### Health Check

```http
GET /api/v1/health
```

**Response (200 OK):**
```json
{
  "status": "healthy",
  "timestamp": "2026-02-16T10:00:00Z",
  "version": "1.0.0"
}
```

### Readiness Check

```http
GET /api/v1/ready
```

**Response (200 OK):**
```json
{
  "ready": true,
  "timestamp": "2026-02-16T10:00:00Z"
}
```

**Response (503 Service Unavailable):**
```json
{
  "ready": false,
  "timestamp": "2026-02-16T10:00:00Z"
}
```

---

## Error Responses

All endpoints use FastAPI's standard error response format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common HTTP Status Codes

| Code | Meaning |
|------|---------|
| `200 OK` | Request succeeded |
| `400 Bad Request` | Invalid request data (e.g., unsupported language, duplicate config) |
| `404 Not Found` | Resource not found |
| `422 Unprocessable Entity` | Validation error (Pydantic schema validation failed) |
| `500 Internal Server Error` | Server error |
| `503 Service Unavailable` | Service not ready (e.g., template service not initialized) |

### Validation Error Format (422)

When Pydantic validation fails, the response includes detailed field-level errors:

```json
{
  "detail": [
    {
      "loc": ["body", "languages", 0],
      "msg": "Unsupported language 'ruby'. Supported languages are: python, java, node, cpp",
      "type": "value_error"
    }
  ]
}
```
