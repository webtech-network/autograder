# API Documentation

The Autograder provides a FastAPI-based REST API for integration with learning management systems.

## Starting the API

```bash
# Development
uvicorn web.main:app --reload

# Production
docker-compose up
```

API documentation available at: `http://localhost:8000/docs`

## Core Endpoints

### Create Grading Configuration

```http
POST /api/v1/grading-configs
Content-Type: application/json

{
  "assignment_id": 42,
  "template_name": "input_output",
  "criteria": {
    "base": { ... }
  },
  "feedback_config": { ... },
  "setup_config": { ... }
}
```

**Response:**
```json
{
  "id": 1,
  "assignment_id": 42,
  "template_name": "input_output",
  "created_at": "2026-02-16T10:00:00Z"
}
```

### Submit for Grading

```http
POST /api/v1/submissions
Content-Type: application/json

{
  "assignment_id": 42,
  "username": "student123",
  "user_id": 1,
  "files": [
    {
      "filename": "main.py",
      "content": "print('Hello World')"
    }
  ],
  "language": "python"
}
```

**Response:**
```json
{
  "submission_id": 1,
  "status": "pending",
  "submitted_at": "2026-02-16T10:05:00Z"
}
```

### Get Results

```http
GET /api/v1/submissions/{submission_id}
```

**Response (Success):**
```json
{
  "id": 1,
  "grading_config_id": 7,
  "external_user_id": "user_001",
  "username": "student123",
  "status": "completed",
  "submitted_at": "2026-02-16T10:05:00Z",
  "graded_at": "2026-02-16T10:05:03Z",
  "final_score": 85.5,
  "feedback": "## Grade: 85.5/100\n\n### ✅ Base Tests...",
  "result_tree": {
    "final_score": 85.5,
    "children": {
      "base": { ... }
    }
  },
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
        "name": "PRE_FLIGHT",
        "status": "success",
        "message": "All preflight checks passed"
      },
      {
        "name": "GRADE",
        "status": "success",
        "message": "Grading completed: 85.5/100"
      }
    ]
  },
  "submission_files": { ... },
  "submission_metadata": null
}
```

**Response (Preflight Failure):**
```json
{
  "id": 2,
  "status": "failed",
  "final_score": 0,
  "feedback": "## Preflight Check Failed\n\n### Setup Command Failed: Compile Calculator.java\n\n**Command executed:**\n```bash\njavac Calculator.java\n```\n\n**Exit code:** 1\n\n**Error output:**\n```\nCalculator.java:4: error: ';' expected\n```\n\n**What to do:**\n- Fix the compilation errors shown above...",
  "result_tree": null,
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

**Response Fields:**
- `result_tree`: Detailed grading results from GRADE step (null if grading didn't occur)
- `pipeline_execution`: Complete pipeline execution details including all steps
- `feedback`: Human-readable feedback (automatically generated for preflight failures)

### List Submissions

```http
GET /api/v1/submissions?assignment_id=42&username=student123
```

**Query Parameters:**
- `assignment_id` (optional): Filter by assignment
- `username` (optional): Filter by student
- `limit` (optional): Number of results (default: 50)
- `offset` (optional): Pagination offset (default: 0)

**Response:**
```json
{
  "submissions": [
    {
      "submission_id": 1,
      "assignment_id": 42,
      "username": "student123",
      "final_score": 85.5,
      "status": "completed",
      "submitted_at": "2026-02-16T10:05:00Z"
    }
  ],
  "total": 1
}
```

### Get Grading Configuration

```http
GET /api/v1/grading-configs/{assignment_id}
```

**Response:**
```json
{
  "id": 1,
  "assignment_id": 42,
  "template_name": "input_output",
  "criteria": { ... },
  "feedback_config": { ... },
  "setup_config": { ... }
}
```

## Authentication

Currently, the API uses simple token-based authentication. Include your API token in the request headers:

```http
Authorization: Bearer YOUR_API_TOKEN
```

## Error Responses

All endpoints follow a consistent error response format:

```json
{
  "detail": "Error message describing what went wrong",
  "error_code": "SPECIFIC_ERROR_CODE",
  "timestamp": "2026-02-16T10:00:00Z"
}
```

### Common HTTP Status Codes

- `200 OK`: Request succeeded
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Missing or invalid authentication
- `404 Not Found`: Resource not found
- `422 Unprocessable Entity`: Validation error
- `500 Internal Server Error`: Server error

## Rate Limiting

API endpoints are rate-limited to ensure fair usage:

- **Default limit**: 100 requests per minute per IP
- **Burst limit**: 200 requests per minute

Rate limit headers are included in responses:
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1645012800
```

## Webhooks

Configure webhooks to receive notifications when grading completes:

```http
POST /api/v1/webhooks
Content-Type: application/json

{
  "url": "https://your-system.com/webhook",
  "events": ["submission.completed", "submission.failed"],
  "secret": "your_webhook_secret"
}
```

When a submission completes, you'll receive a POST request:

```json
{
  "event": "submission.completed",
  "submission_id": 1,
  "assignment_id": 42,
  "username": "student123",
  "final_score": 85.5,
  "timestamp": "2026-02-16T10:05:03Z"
}
```

