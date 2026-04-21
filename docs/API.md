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

## Authentication

Most endpoints are public and require no authentication. Two endpoints designed for machine-to-machine integration (GitHub Action external mode) are protected with a Bearer token.

### Protected Endpoints

| Endpoint | Method |
|----------|--------|
| `/api/v1/configs/id/{config_id}` | GET |
| `/api/v1/submissions/external-results` | POST |

### Setup

Set the `AUTOGRADER_INTEGRATION_TOKEN` environment variable on the server:

```bash
# Generate a strong random token
export AUTOGRADER_INTEGRATION_TOKEN=$(openssl rand -hex 32)
```

When the variable is **not set or empty**, the server will fail to start the integration auth configuration and protected endpoints will return `503 Service Unavailable`. The token **must** be configured and non-empty before using integration endpoints.

### Usage

Include the token in the `Authorization` header:

```bash
curl -H "Authorization: Bearer $AUTOGRADER_INTEGRATION_TOKEN" \
     http://localhost:8000/api/v1/configs/id/1
```

### Error Responses

| Status | Condition |
|--------|-----------|
| `401 Unauthorized` | Missing or invalid token |

---

## Endpoints Overview

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| `POST` | `/api/v1/configs` | Create a grading configuration | |
| `GET` | `/api/v1/configs` | List all grading configurations | |
| `GET` | `/api/v1/configs/id/{config_id}` | Get configuration by internal ID | ✓ |
| `GET` | `/api/v1/configs/{external_assignment_id}` | Get configuration by assignment ID | |
| `PUT` | `/api/v1/configs/{config_id}` | Update a grading configuration | |
| `PUT` | `/api/v1/configs/external/{external_assignment_id}` | Update a grading configuration by external assignment ID | |
| `POST` | `/api/v1/submissions` | Submit code for grading | |
| `GET` | `/api/v1/submissions/{submission_id}` | Get submission details and results | |
| `GET` | `/api/v1/submissions/user/{external_user_id}` | List submissions by user | |
| `POST` | `/api/v1/submissions/external-results` | Ingest externally computed grading results | ✓ |
| `POST` | `/api/v1/execute` | Execute code without grading (DCE) | |
| `GET` | `/api/v1/templates` | List available grading templates | |
| `GET` | `/api/v1/templates/{template_name}` | Get template details | |
| `GET` | `/api/v1/health` | Health check | |
| `GET` | `/api/v1/ready` | Readiness check | |

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
  },
  "include_feedback": true,
  "feedback_config": {
    "general": {
      "report_title": "Evaluation Report",
      "show_score": true,
      "show_passed_tests": false,
      "add_report_summary": true,
      "online_content": [
        {
          "url": "https://docs.python.org/3/tutorial/",
          "description": "Python Tutorial"
        }
      ]
    }
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
| `include_feedback` | boolean | ✗ | Whether to generate a feedback report after grading (default: `true`) |
| `feedback_config` | object | ✗ | Feedback preferences — see [FeedbackConfig Reference](#feedbackconfig-reference) |

**Response (201 Created):**
```json
{
  "id": 1,
  "external_assignment_id": "assignment-42",
  "template_name": "input_output",
  "criteria_config": { ... },
  "languages": ["python", "java"],
  "setup_config": { ... },
  "include_feedback": true,
  "feedback_config": { ... },
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

### Get Grading Configuration by Internal ID

```http
GET /api/v1/configs/id/{config_id}
Authorization: Bearer <token>
```

>  **Protected** — requires a valid integration token (see [Authentication](#authentication)).

Fetch a grading configuration using its internal database ID. This is used by external/private mode (e.g. GitHub Action) when only the `grading_config_id` is known.

**Response (200 OK):**
```json
{
  "id": 1,
  "external_assignment_id": "assignment-42",
  "template_name": "input_output",
  "criteria_config": { ... },
  "languages": ["python", "java"],
  "setup_config": { ... },
  "include_feedback": true,
  "feedback_config": { ... },
  "version": 1,
  "created_at": "2026-02-16T10:00:00Z",
  "updated_at": "2026-02-16T10:00:00Z",
  "is_active": true
}
```

**Error (404):** Configuration not found.

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
  "include_feedback": false,
  "feedback_config": { ... },
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
  "include_feedback": true,
  "feedback_config": { ... },
  "is_active": false
}
```

**Response (200 OK):** Updated configuration object (same schema as the create response).

**Error (404):** Configuration not found for the supplied `external_assignment_id`.

---

## FeedbackConfig Reference

The `feedback_config` object controls how the `DefaultReporter` generates the post-grading Markdown report. All fields are optional.

```json
{
  "general": {
    "report_title": "Evaluation Report",
    "show_score": true,
    "show_passed_tests": false,
    "add_report_summary": true,
    "online_content": [
      {
        "url": "https://docs.python.org/3/tutorial/",
        "description": "Python Official Tutorial"
      }
    ]
  },
  "default": {
    "category_headers": {
      "base": "✅ Essential Requirements",
      "penalty": "❌ Points to Improve",
      "bonus": "⭐ Extra Points"
    }
  }
}
```

### `general` fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `report_title` | string | `"Evaluation Report"` | Custom title at the top of the report |
| `show_score` | boolean | `true` | Append the final score section at the bottom of the report |
| `show_passed_tests` | boolean | `false` | Include tests that passed (score = 100) in the results |
| `add_report_summary` | boolean | `true` | Add a summary section with template name and score breakdown |
| `online_content` | list[object] | `[]` | Learning resources appended at the end of the report |

### `online_content` object fields

| Field | Type | Description |
|-------|------|--------------|
| `url` | string | Full URL of the resource |
| `description` | string | Human-readable label for the link |
| `linked_tests` | list[string] | Optional: List of test names. If provided, the resource is only shown if at least one of these tests fails. |

Resources without `linked_tests` are always displayed at the end of the report. Resources with `linked_tests` act as "targeted hints" that only appear when relevant.

### `default` fields

| Field | Type | Description |
|-------|------|-------------|
| `category_headers` | object | Override section headers per category (`base`, `penalty`, `bonus`) |

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
        "name": "SANDBOX",
        "status": "success",
        "message": "Sandbox created and attached to pipeline"
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

### Ingest External Grading Results

```http
POST /api/v1/submissions/external-results
Content-Type: application/json
Authorization: Bearer <token>
```

> 🔒 **Protected** — requires a valid integration token (see [Authentication](#authentication)).

Persist grading results computed outside the cloud instance (e.g. GitHub Action running in external/private mode). Creates both a `submission` and a `submission_result` row, making the result visible through the standard submission retrieval endpoints.

**Request Body:**
```json
{
  "grading_config_id": 1,
  "external_user_id": "user_001",
  "username": "student123",
  "language": "python",
  "status": "completed",
  "final_score": 85.5,
  "feedback": "## Grade: 85.5/100\n...",
  "result_tree": { ... },
  "focus": { ... },
  "pipeline_execution": { ... },
  "execution_time_ms": 4521,
  "error_message": null,
  "submission_metadata": {
    "repo": "org/repo",
    "run_id": "123"
  }
}
```

**Request Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `grading_config_id` | int | ✓ | Internal grading configuration ID |
| `external_user_id` | string | ✓ | External user ID from your platform |
| `username` | string | ✓ | Username of the submitter |
| `language` | string | ✓ | Language used for grading (must be supported by the config) |
| `status` | string | ✓ | `completed` or `failed` |
| `final_score` | float | ✓ | Final grading score (≥ 0) |
| `feedback` | string | ✗ | Generated feedback text |
| `result_tree` | object | ✗ | Scored result tree |
| `focus` | object | ✗ | Failed tests sorted by impact |
| `pipeline_execution` | object | ✗ | Pipeline step execution details |
| `execution_time_ms` | int | ✓ | Total execution time in milliseconds (≥ 0) |
| `error_message` | string | ✗ | Error message for failed runs |
| `submission_metadata` | object | ✗ | Repository/run metadata |

**Response (200 OK):**
```json
{
  "submission_id": 5,
  "grading_config_id": 1,
  "external_user_id": "user_001",
  "username": "student123",
  "status": "completed",
  "final_score": 85.5,
  "graded_at": "2026-02-16T10:05:03Z",
  "execution_time_ms": 4521
}
```

**Errors:**
- `404`: Grading configuration not found
- `400`: Language not supported for this configuration
- `422`: Validation error (invalid status, negative score, missing required fields)

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

## External Mode Integration

This section describes how the Autograder GitHub Action in **external mode** interacts with the API. The action makes exactly two authenticated calls per grading run.

### Integration sequence

```
1. GET  /api/v1/configs/id/{grading_config_id}     # fetch grading config
2. POST /api/v1/submissions/external-results        # submit result (or failure)
```

Both endpoints require the `Authorization: Bearer <token>` header where the token matches `AUTOGRADER_INTEGRATION_TOKEN` on the server.

### Config fetch

```http
GET /api/v1/configs/id/{grading_config_id}
Authorization: Bearer <token>
```

Returns the full grading configuration object (see [Get Grading Configuration by Internal ID](#get-grading-configuration-by-internal-id)). The action uses the following fields from the response:

| Field | Used for |
|-------|----------|
| `id` | Sent back as `grading_config_id` in the result payload |
| `template_name` | Selects the grading template |
| `criteria_config` | Grading rubric |
| `languages` | Validates `submission-language`; defaults to `languages[0]` if omitted |
| `include_feedback` | Whether to run the feedback step |
| `setup_config` | Pre-flight setup commands and required files |
| `feedback_config` | Reporter configuration |

### Result submission (success)

```http
POST /api/v1/submissions/external-results
Authorization: Bearer <token>
Content-Type: application/json

{
  "grading_config_id": 42,
  "external_user_id": "github-actor-login",
  "username": "github-actor-login",
  "language": "python",
  "status": "completed",
  "final_score": 85.5,
  "feedback": "## Grade: 85.5/100\n...",
  "result_tree": { ... },
  "focus": { ... },
  "pipeline_execution": { ... },
  "execution_time_ms": 3200,
  "error_message": null,
  "submission_metadata": {
    "repository": "org/repo",
    "commit_sha": "abc123",
    "run_id": "999",
    "actor": "student1",
    "ref": "refs/heads/main"
  }
}
```

### Result submission (failure)

When grading fails, the action posts a failure payload before exiting non-zero:

```json
{
  "grading_config_id": 42,
  "external_user_id": "github-actor-login",
  "username": "github-actor-login",
  "language": "python",
  "status": "failed",
  "final_score": 0.0,
  "feedback": null,
  "result_tree": null,
  "focus": null,
  "pipeline_execution": null,
  "execution_time_ms": 1500,
  "error_message": "Sandbox timed out after 30 s",
  "submission_metadata": { ... }
}
```

### Error handling

| Scenario | Action behaviour |
|----------|-----------------|
| `401` on config fetch | Exits non-zero; no result posted |
| `404` on config fetch | Exits non-zero; no result posted |
| 5xx / network error on config fetch | Retries with exponential back-off; then exits non-zero |
| Grading raises exception | Posts failure payload, then exits non-zero |
| `401` / `4xx` on result submission | Exits non-zero (failure recorded in Action log) |

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
