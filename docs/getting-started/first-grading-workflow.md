# Run Your First Grading Workflow

This quickstart walks you through one complete grading cycle:

1. start the API
2. create a grading configuration
3. submit student code
4. fetch the graded result

## Prerequisites

- Docker and Docker Compose installed
- The repository set up as in the [Development Guide](../guides/development.md#setup)

## 1) Start Autograder

```bash
export SANDBOX_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
make start-autograder
```

The API and its private sandbox control service share that token. When ready,
the API is available at `http://localhost:8000`. Every route except health,
readiness and the template catalog requires a bearer token
([AUTH.md](../contracts/AUTH.md)); the development compose file sets the
integration token to `e2e-test-token`:

```bash
export TOKEN=e2e-test-token
```

You can check health (public):

```bash
curl http://localhost:8000/api/v1/health
```

## 2) Create a grading configuration

A configuration is an assignment alias plus one
[v1 grading definition](../contracts/DEFINITIONS.md):

```bash
curl -X POST http://localhost:8000/api/v1/configs \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "external_assignment_id": "demo-assignment-1",
    "definition": {
      "schema_version": "1.0",
      "templates": ["input_output"],
      "languages": ["python"],
      "criteria": {
        "base": {
          "weight": 100,
          "subjects": [{
            "subject_name": "Functionality",
            "weight": 100,
            "tests": [{
              "id": "greets",
              "type": "expect_output",
              "name": "Greets the user",
              "parameters": {
                "inputs": ["Alice"],
                "expected_output": "Hello, Alice!",
                "program_command": "python3 main.py"
              }
            }]
          }]
        }
      },
      "preparation": {"languages": {"python": {"required_files": ["main.py"]}}},
      "feedback": {"enabled": true, "mode": "default"}
    }
  }'
```

## 3) Submit a student solution

```bash
curl -i -X POST http://localhost:8000/api/v1/submissions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Idempotency-Key: demo-student-1-attempt-1" \
  -H "Content-Type: application/json" \
  -d '{
    "external_assignment_id": "demo-assignment-1",
    "external_user_id": "student-1",
    "username": "student_1",
    "files": [
      {
        "filename": "main.py",
        "content": "name = input().strip()\nprint(f\"Hello, {name}!\")"
      }
    ]
  }'
```

The response is `202 Accepted` with a `Location` header for polling. The single
allowed language is inferred. Repeating the request with the same
`Idempotency-Key` returns the same submission instead of grading again
([REPLAY.md](../contracts/REPLAY.md)).

## 4) Poll for the result

```bash
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/submissions/<submission_id>
```

The compact poll reports the status, `final_score`, provenance and feedback
status. The full terminal [outcome](../contracts/OUTCOMES.md) (score tree and
rendered feedback) is returned by the details endpoint:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/v1/submissions/<submission_id>/details
```

## What you just exercised

You ran the full core flow:

`validate -> acquire/prepare? -> assess (one AI batch) -> grade -> requested feedback? -> close -> outcome`

To understand each stage in depth, continue with [Pipeline Architecture](../core/pipeline-architecture.md)
and the [responsibility map](../architecture/overview.md).
