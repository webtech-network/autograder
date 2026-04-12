# Run Your First Grading Workflow

This quickstart walks you through one complete grading cycle:

1. start the API
2. create a grading configuration
3. submit student code
4. fetch the graded result

## Prerequisites

- Docker and Docker Compose installed
- Python available on your machine
- Project dependencies installed (`pip install -r requirements.txt`)

## 1) Start Autograder

```bash
make start-autograder
```

When ready, the API is available at `http://localhost:8080`.

You can check health:

```bash
curl http://localhost:8080/api/v1/health
```

## 2) Create a grading configuration

```bash
curl -X POST http://localhost:8080/api/v1/configs \
  -H "Content-Type: application/json" \
  -d '{
    "external_assignment_id": "demo-assignment-1",
    "template_name": "input_output",
    "criteria_config": {
      "base": {
        "weight": 100,
        "subjects": [
          {
            "subject_name": "Functionality",
            "weight": 100,
            "tests": [
              {
                "name": "expect_output",
                "weight": 100,
                "parameters": {
                  "inputs": ["Alice"],
                  "expected_output": "Hello, Alice!",
                  "program_command": "python3 main.py"
                }
              }
            ]
          }
        ]
      }
    },
    "languages": ["python"],
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
        "add_report_summary": true
      }
    }
  }'
```

## 3) Submit a student solution

```bash
curl -X POST http://localhost:8080/api/v1/submissions \
  -H "Content-Type: application/json" \
  -d '{
    "external_assignment_id": "demo-assignment-1",
    "external_user_id": "student-1",
    "username": "student_1",
    "language": "python",
    "files": [
      {
        "filename": "main.py",
        "content": "name = input().strip()\nprint(f\"Hello, {name}!\")"
      }
    ]
  }'
```

Copy the returned `id` from the response. That is your `submission_id`.

## 4) Poll for the result

```bash
curl http://localhost:8080/api/v1/submissions/<submission_id>
```

When grading finishes, response status becomes `completed`, and you will get:

- `final_score`
- `feedback`
- `result_tree`
- `focus`

## What you just exercised

You ran the full core flow:

`LOAD_TEMPLATE -> BUILD_TREE -> SANDBOX -> PRE_FLIGHT -> GRADE -> FOCUS -> FEEDBACK`

To understand each stage in depth, continue with [Pipeline Architecture](../core/pipeline-architecture.md).
