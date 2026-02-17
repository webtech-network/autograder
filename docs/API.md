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

**Response:**
```json
{
  "submission_id": 1,
  "final_score": 85.5,
  "status": "completed",
  "feedback": "...",
  "result_tree": { ... },
  "completed_at": "2026-02-16T10:05:03Z"
}
```

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

