# 🚀 Autograder API - Quick Reference Card

## 📍 Endpoints

```
POST /grade_submission/    # Grade a student submission
GET  /template/{name}      # Get template information
```

## 🎯 Template Types

| Template | Preset Name | Files Required | Setup Required |
|----------|-------------|----------------|----------------|
| Web Dev  | `web`       | HTML/CSS/JS    | ❌ No          |
| API Test | `api`       | server.js, package.json | ✅ Yes (setup.json) |
| I/O Test | `io`        | Python/executable | ✅ Yes (setup.json) |
| Essay    | `essay`     | README.md, .md/.txt | ❌ No          |
| Custom   | `custom`    | Any + template.py | ⚠️ Optional |

## 📤 Request Format

### Web Dev Example
```bash
curl -X POST http://localhost:8001/grade_submission/ \
  -F "submission_files=@index.html" \
  -F "submission_files=@style.css" \
  -F "criteria_json=@criteria.json" \
  -F "feedback_json=@feedback.json" \
  -F "template_preset=web" \
  -F "student_name=John Doe" \
  -F "student_credentials=token-123" \
  -F "include_feedback=true" \
  -F "feedback_type=default"
```

### API Test Example
```bash
curl -X POST http://localhost:8001/grade_submission/ \
  -F "submission_files=@server.js" \
  -F "submission_files=@package.json" \
  -F "criteria_json=@criteria.json" \
  -F "setup_json=@setup.json" \
  -F "template_preset=api" \
  -F "student_name=Jane Smith" \
  -F "student_credentials=token-456" \
  -F "include_feedback=true"
```

## 📥 Response Format

```json
{
  "server_status": "Server connection happened successfully",
  "autograding_status": "completed",
  "final_score": 92.5,
  "feedback": "Great work! ...",
  "test_report": [
    {
      "name": "test_name",
      "score": 100,
      "report": "Test passed",
      "parameters": {}
    }
  ]
}
```

## 🧪 Testing Commands

### Using Makefile (Recommended)
```bash
# Run all API tests
make run-api-tests

# Run specific template tests
make run-api-tests web      # Web Dev template only
make run-api-tests api      # API Testing template only
make run-api-tests io       # Input/Output template only
make run-api-tests essay    # Essay template only
make run-api-tests custom   # Custom template only
```

### Using Python Script Directly
```bash
# Python script (interactive)
python test_api_requests.py

# Python script (specific test)
python test_api_requests.py --test web
python test_api_requests.py --test api
python test_api_requests.py --test io
python test_api_requests.py --test essay
python test_api_requests.py --test custom
python test_api_requests.py --test all
```

### Using Bash Script
```bash
./tests/data/curl_examples.sh
./tests/data/curl_examples.sh --web
./tests/data/curl_examples.sh --all
```

## 📋 Required Fields

| Field | Type | Always Required | Notes |
|-------|------|-----------------|-------|
| `submission_files` | File[] | ✅ Yes | Student code |
| `template_preset` | String | ✅ Yes | Template type |
| `student_name` | String | ✅ Yes | Student identifier |
| `student_credentials` | String | ✅ Yes | Auth token |
| `include_feedback` | Boolean | ✅ Yes | Enable feedback |
| `criteria_json` | File | ✅ Yes | Grading rules |
| `feedback_json` | File | ⚠️ Recommended | Feedback config |
| `setup_json` | File | ⚠️ For api/io | Docker config |
| `custom_template` | File | ⚠️ For custom | Template code |

## 🗂️ Test Data Locations

```
tests/data/
├── web_dev/         # HTML/CSS/JS test
├── api_testing/     # Node.js API test
├── input_output/    # Python I/O test
├── essay/           # Essay grading test
└── custom_template/ # Custom template test
```

## 🔍 Criteria.json Format

```json
{
  "base": {
    "weight": 100,
    "subjects": {
      "subject_name": {
        "weight": 50,
        "tests": [
          {
            "name": "test_function",
            "file": "filename.ext",
            "calls": [["param1", "param2"]]
          }
        ]
      }
    }
  }
}
```

## ⚙️ Setup.json Format (for api/io)

```json
{
  "runtime_image": "node:18-alpine",
  "container_port": 8000,
  "start_command": "node server.js",
  "commands": {
    "install_dependencies": "npm install"
  }
}
```

## 🎨 Common Tests by Template

### Web Dev Tests
- `has_tag` - Check HTML tags
- `has_semantic_tag` - Check semantic HTML
- `has_class` - Check CSS classes
- `check_css_property` - Validate CSS
- `check_js_feature` - Find JS features

### API Tests
- `health_check` - Endpoint health
- `check_response_json` - JSON validation
- `check_post_request` - POST handling

### I/O Tests
- `expect_output` - Validate program output

## 🚦 Status Codes

| Code | Meaning |
|------|---------|
| 200  | Success |
| 400  | Bad request (missing fields) |
| 404  | Template not found |
| 500  | Server error |

## 💻 Python Usage Example

```python
import requests

files = [
    ('submission_files', ('index.html', open('index.html', 'rb'))),
    ('criteria_json', ('criteria.json', open('criteria.json', 'rb')))
]

data = {
    'template_preset': 'web',
    'student_name': 'John Doe',
    'student_credentials': 'token-123',
    'include_feedback': 'true'
}

response = requests.post(
    'http://localhost:8001/grade_submission/',
    files=files,
    data=data
)

print(response.json())
```

## 🐳 Docker Setup

### API Template
```json
{
  "runtime_image": "node:18-alpine",
  "container_port": 8000,
  "start_command": "node server.js"
}
```

### I/O Template
```json
{
  "runtime_image": "python:3.11-slim",
  "start_command": "python program.py"
}
```

## 🔥 Quick Troubleshooting

| Error | Solution |
|-------|----------|
| Connection refused | Start API: `python api_entrypoint.py` |
| File not found | Run from project root |
| Docker error | Check Docker: `docker ps` |
| Timeout | Increase timeout in script |
| Invalid JSON | Validate with `jq` |

## 📊 Score Interpretation

- **100**: Perfect score
- **75-99**: Good, minor issues
- **50-74**: Needs improvement
- **0-49**: Major issues
- **0**: Failed completely

## 🔗 Useful Links

- Full Guide: `API_TEST_SUITE_GUIDE.md`
- Test Data Docs: `tests/data/README.md`
- Postman Collection: `tests/data/Autograder_API_Collection.postman_collection.json`

---

**Quick Start:** 
- Makefile: `make run-api-tests` or `make run-api-tests web`
- Python: `python test_api_requests.py`
