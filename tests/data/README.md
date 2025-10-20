# Autograder API Test Suite

This directory contains comprehensive test data and a testing script for the Autograder API. The test suite covers all supported template types and provides realistic submission scenarios.

## 📁 Directory Structure

```
tests/data/
├── web_dev/              # Web Development template test data
│   ├── index.html        # Student HTML submission
│   ├── style.css         # Student CSS submission
│   ├── script.js         # Student JavaScript submission
│   ├── criteria.json     # Grading criteria configuration
│   └── feedback.json     # Feedback configuration
│
├── api_testing/          # API Testing template test data
│   ├── server.js         # Student Node.js API server
│   ├── package.json      # NPM dependencies
│   ├── criteria.json     # API testing criteria
│   ├── feedback.json     # Feedback configuration
│   └── setup.json        # Container setup (runtime, commands)
│
├── input_output/         # Input/Output template test data
│   ├── calculator.py     # Student Python program
│   ├── requirements.txt  # Python dependencies
│   ├── criteria.json     # I/O testing criteria
│   ├── feedback.json     # Feedback configuration
│   └── setup.json        # Container setup
│
├── essay/                # Essay template test data
│   ├── essay.txt         # Student essay text
│   ├── criteria.json     # Essay grading criteria
│   └── feedback.json     # Feedback configuration
│
└── custom_template/      # Custom Template test data
    ├── main.py           # Student Python submission
    ├── custom_template.py # Custom grading template
    ├── criteria.json     # Custom criteria
    └── feedback.json     # Feedback configuration
```

## 🚀 Quick Start

### Prerequisites

```bash
# Install required Python package
pip install requests
```

### Running Tests

**Interactive Menu Mode:**
```bash
python test_api_requests.py
```

**Direct Test Execution:**
```bash
# Test specific template
python test_api_requests.py --test web
python test_api_requests.py --test api
python test_api_requests.py --test io
python test_api_requests.py --test essay
python test_api_requests.py --test custom

# Run all tests
python test_api_requests.py --test all
```

**Custom API URL:**
```bash
python test_api_requests.py --url http://api.example.com:8000
```

## 📋 API Endpoints

### 1. Grade Submission (POST)

**Endpoint:** `/grade_submission/`

**Request Format:**
- Method: `POST`
- Content-Type: `multipart/form-data`

**Form Fields:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `submission_files` | File[] | ✅ | Student's source code files |
| `template_preset` | String | ✅ | Template type: "web dev", "api", "io", "essay", "custom" |
| `student_name` | String | ✅ | Student's name |
| `student_credentials` | String | ✅ | GitHub token or credentials |
| `include_feedback` | Boolean | ✅ | Whether to include detailed feedback |
| `criteria_json` | File | ✅ | JSON file with grading criteria |
| `feedback_type` | String | ⚠️ | "default" or "ai" (default: "default") |
| `feedback_json` | File | ⚠️ | JSON file with feedback configuration |
| `setup_json` | File | ⚠️ | JSON file for container setup (required for api/io) |
| `custom_template` | File | ⚠️ | Python file with custom template (required for "custom") |
| `openai_key` | String | ⚠️ | OpenAI API key (for AI feedback) |
| `redis_url` | String | ⚠️ | Redis URL (for AI feedback caching) |
| `redis_token` | String | ⚠️ | Redis token |

**Response Format:**
```json
{
  "server_status": "Server connection happened successfully",
  "autograding_status": "completed",
  "final_score": 85.5,
  "feedback": "...",
  "test_report": [
    {
      "name": "has_tag",
      "score": 100,
      "report": "Found 5 of 5 required div tags",
      "parameters": {"tag": "div", "required_count": 5}
    }
  ]
}
```

### 2. Get Template Info (GET)

**Endpoint:** `/template/{template_name}`

**Example:**
```bash
GET /template/web_dev
GET /template/api
GET /template/io
GET /template/essay
```

**Response:** Returns template metadata including available tests and their parameters.

## 📦 Payload Examples

### 1. Web Development Template

**Template:** `web dev`  
**Files:** HTML, CSS, JavaScript  
**No Setup Required:** Tests run directly on static files

**Payload Structure:**
```python
files = [
    ('submission_files', ('index.html', html_content, 'text/plain')),
    ('submission_files', ('style.css', css_content, 'text/plain')),
    ('submission_files', ('script.js', js_content, 'text/plain')),
    ('criteria_json', ('criteria.json', criteria_content, 'application/json')),
    ('feedback_json', ('feedback.json', feedback_content, 'application/json'))
]

data = {
    'template_preset': 'web dev',
    'student_name': 'John Doe',
    'student_credentials': 'token-123',
    'include_feedback': 'true',
    'feedback_type': 'default'
}
```

**Criteria Example:**
```json
{
  "base": {
    "weight": 100,
    "subjects": {
      "html_structure": {
        "weight": 40,
        "tests": [
          {
            "name": "has_tag",
            "file": "index.html",
            "calls": [
              ["div", 5],
              ["h1", 2],
              ["p", 3]
            ]
          }
        ]
      }
    }
  }
}
```

### 2. API Testing Template

**Template:** `api`  
**Files:** server.js, package.json  
**Requires:** setup.json with Docker configuration

**Payload Structure:**
```python
files = [
    ('submission_files', ('server.js', server_content, 'text/plain')),
    ('submission_files', ('package.json', package_content, 'text/plain')),
    ('criteria_json', ('criteria.json', criteria_content, 'application/json')),
    ('feedback_json', ('feedback.json', feedback_content, 'application/json')),
    ('setup_json', ('setup.json', setup_content, 'application/json'))
]

data = {
    'template_preset': 'api',
    'student_name': 'Jane Smith',
    'student_credentials': 'token-456',
    'include_feedback': 'true',
    'feedback_type': 'default'
}
```

**Setup Example:**
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

**Criteria Example:**
```json
{
  "base": {
    "weight": 100,
    "subjects": {
      "api_endpoints": {
        "weight": 100,
        "tests": [
          {
            "name": "health_check",
            "calls": [["/health"]]
          },
          {
            "name": "check_response_json",
            "calls": [
              ["/api/user/1", "id", 1],
              ["/api/user/1", "name", "John Doe"]
            ]
          }
        ]
      }
    }
  }
}
```

### 3. Input/Output Template

**Template:** `io`  
**Files:** Python script, requirements.txt  
**Requires:** setup.json with Docker configuration

**Payload Structure:**
```python
files = [
    ('submission_files', ('calculator.py', program_content, 'text/plain')),
    ('submission_files', ('requirements.txt', requirements, 'text/plain')),
    ('criteria_json', ('criteria.json', criteria_content, 'application/json')),
    ('feedback_json', ('feedback.json', feedback_content, 'application/json')),
    ('setup_json', ('setup.json', setup_content, 'application/json'))
]

data = {
    'template_preset': 'io',
    'student_name': 'Bob Johnson',
    'student_credentials': 'token-789',
    'include_feedback': 'true',
    'feedback_type': 'default'
}
```

**Criteria Example:**
```json
{
  "base": {
    "weight": 100,
    "subjects": {
      "basic_operations": {
        "weight": 100,
        "tests": [
          {
            "name": "expect_output",
            "calls": [
              [["add", "5", "3"], "8"],
              [["subtract", "10", "4"], "6"]
            ]
          }
        ]
      }
    }
  }
}
```

### 4. Essay Template

**Template:** `essay`  
**Files:** Plain text essay  
**No Setup Required:** Graded based on text content

**Payload Structure:**
```python
files = [
    ('submission_files', ('essay.txt', essay_content, 'text/plain')),
    ('criteria_json', ('criteria.json', criteria_content, 'application/json')),
    ('feedback_json', ('feedback.json', feedback_content, 'application/json'))
]

data = {
    'template_preset': 'essay',
    'student_name': 'Chris Lee',
    'student_credentials': 'token-202',
    'include_feedback': 'true',
    'feedback_type': 'default'
}
```

**Criteria Example:**
```json
{
  "base": {
    "weight": 100,
    "subjects": {
      "content_quality": {
        "weight": 70,
        "tests": [
          {
            "name": "check_keyword",
            "file": "essay.txt",
            "calls": [
              ["introduction", 1],
              ["conclusion", 1]
            ]
          }
        ]
      }
    }
  }
}
```

### 5. Custom Template

**Template:** `custom`  
**Files:** Student submission + custom_template.py  
**Requires:** Custom Python template file

**Payload Structure:**
```python
files = [
    ('submission_files', ('main.py', student_code, 'text/plain')),
    ('criteria_json', ('criteria.json', criteria_content, 'application/json')),
    ('feedback_json', ('feedback.json', feedback_content, 'application/json')),
    ('custom_template', ('template.py', template_code, 'text/plain'))
]

data = {
    'template_preset': 'custom',
    'student_name': 'Alice Williams',
    'student_credentials': 'token-101',
    'include_feedback': 'true',
    'feedback_type': 'default'
}
```

## 🧪 Test Scenarios

### Scenario 1: Web Development Portfolio
Tests HTML structure, CSS styling, and JavaScript functionality for a student portfolio website.

**Expected Results:**
- ✅ HTML semantic tags detected
- ✅ CSS classes and properties validated
- ✅ JavaScript event listeners found
- ✅ No console errors

### Scenario 2: REST API Server
Tests a Node.js Express API with multiple endpoints and JSON responses.

**Expected Results:**
- ✅ Health check endpoint responds
- ✅ User data endpoints return correct JSON
- ✅ POST requests create resources

### Scenario 3: Python Calculator
Tests a command-line calculator program with various mathematical operations.

**Expected Results:**
- ✅ Addition operation works correctly
- ✅ Subtraction operation works correctly
- ✅ Edge cases handled (division by zero, etc.)

### Scenario 4: Essay Evaluation
Evaluates a student's essay based on content quality, keyword presence, and structure.

**Expected Results:**
- ✅ Introduction and conclusion paragraphs present
- ✅ Required keywords found
- ✅ No spelling or grammar errors

### Scenario 5: Custom Template
Tests a custom grading template that checks for file existence and function definitions.

**Expected Results:**
- ✅ Required files present
- ✅ Required functions defined

## 🔧 Troubleshooting

### Connection Errors
```
❌ ERROR: Could not connect to API at http://localhost:8001
```
**Solution:** Ensure the API server is running:
```bash
cd autograder/connectors/adapters/api
python api_entrypoint.py
```

### Missing Test Data
```
FileNotFoundError: Test directory not found
```
**Solution:** Ensure you're running the script from the project root:
```bash
cd /path/to/autograder
python test_api_requests.py
```

### Timeout Errors
```
❌ ERROR: Request timed out
```
**Solution:** 
- Increase timeout in the script (default: 120 seconds)
- Check if Docker containers are running properly
- Verify network connectivity

## 📊 Understanding Results

### Score Interpretation
- **100**: Perfect score - all tests passed
- **0-99**: Partial score - some tests passed
- **0**: Failed - no tests passed

### Test Report Format
Each test in the report includes:
- `name`: Test function name
- `score`: Score out of 100
- `report`: Human-readable description
- `parameters`: Test parameters used

### Feedback Types
- **default**: Standard feedback based on test results
- **ai**: AI-generated feedback (requires OpenAI API key)

## 🚀 AWS Lambda Deployment

For deploying to AWS Lambda, the payload structure remains the same. However:

1. **Base64 Encoding**: File contents must be base64 encoded
2. **API Gateway**: Use multipart/form-data or JSON with base64 strings
3. **Timeout**: Set Lambda timeout to at least 5 minutes for complex tests
4. **Memory**: Allocate at least 2GB RAM for Docker operations

**Example Lambda Payload:**
```json
{
  "template_preset": "web dev",
  "student_name": "John Doe",
  "student_credentials": "token-123",
  "include_feedback": true,
  "submission_files": [
    {
      "filename": "index.html",
      "content": "base64_encoded_content_here"
    }
  ],
  "criteria": { /* criteria JSON */ },
  "feedback": { /* feedback JSON */ }
}
```

## 📝 Notes

- All test data is realistic and follows best practices
- Tests are designed to pass with provided submissions
- Modify criteria.json to test different scenarios
- Use setup.json for templates requiring runtime environments
- Custom templates must inherit from the Template base class

## 🤝 Contributing

To add new test scenarios:

1. Create a new directory under `tests/data/`
2. Add submission files and configuration JSONs
3. Update `test_api_requests.py` with a new test method
4. Add the test to the interactive menu

## 📚 Additional Resources

- [API Documentation](../docs/api_reference.md)
- [Template Guide](../docs/creating_assignments.md)
- [Configuration Rules](../docs/CONFIGURATION_RULES.md)
