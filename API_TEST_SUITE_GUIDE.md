# Autograder API Testing Suite - Complete Guide

## 📋 Overview

This comprehensive testing suite provides everything developers need to test the Autograder API with realistic payloads aligned to the standard autograder grading package structure. The suite includes:

- ✅ **4 Complete Test Scenarios** (Web Dev, API Testing, I/O, Custom Template)
- ✅ **Realistic Student Submissions** (HTML/CSS/JS, Node.js API, Python programs)
- ✅ **Properly Structured Configuration Files** (criteria.json, feedback.json, setup.json)
- ✅ **Interactive Python Testing Script**
- ✅ **Bash Script with cURL Commands**
- ✅ **Postman Collection for GUI Testing**
- ✅ **Comprehensive Documentation**

## 🚀 Quick Start

### Option 1: Python Script (Recommended)

```bash
# Install dependencies
pip install requests

# Run interactive menu
python test_api_requests.py

# Or run specific test
python test_api_requests.py --test web
python test_api_requests.py --test all
```

### Option 2: Bash Script with cURL

```bash
# Make executable (already done)
chmod +x tests/data/curl_examples.sh

# Run interactive menu
./tests/data/curl_examples.sh

# Or run specific test
./tests/data/curl_examples.sh --web
./tests/data/curl_examples.sh --all
```

### Option 3: Postman

1. Open Postman
2. Import `tests/data/Autograder_API_Collection.postman_collection.json`
3. Update file paths to absolute paths on your system
4. Execute requests

## 📁 Project Structure

```
autograder/
├── test_api_requests.py              # Main Python testing script
│
└── tests/
    └── data/
        ├── README.md                  # Comprehensive documentation
        ├── curl_examples.sh           # Bash testing script
        ├── Autograder_API_Collection.postman_collection.json
        │
        ├── web_dev/                   # Web Development test data
        │   ├── index.html             # Student HTML submission
        │   ├── style.css              # Student CSS submission
        │   ├── script.js              # Student JavaScript submission
        │   ├── criteria.json          # Grading criteria
        │   └── feedback.json          # Feedback configuration
        │
        ├── api_testing/               # API Testing test data
        │   ├── server.js              # Node.js Express API
        │   ├── package.json           # NPM dependencies
        │   ├── criteria.json          # API testing criteria
        │   ├── feedback.json          # Feedback configuration
        │   └── setup.json             # Docker runtime config
        │
        ├── input_output/              # Input/Output test data
        │   ├── calculator.py          # Python calculator program
        │   ├── requirements.txt       # Python dependencies
        │   ├── criteria.json          # I/O testing criteria
        │   ├── feedback.json          # Feedback configuration
        │   └── setup.json             # Docker runtime config
        │
        └── custom_template/           # Custom Template test data
            ├── main.py                # Student Python submission
            ├── custom_template.py     # Custom grading template
            ├── criteria.json          # Custom criteria
            └── feedback.json          # Feedback configuration
```

## 🎯 Test Scenarios

### 1. Web Development Template (`web dev`)

**Description:** Tests a student portfolio website with HTML, CSS, and JavaScript.

**Submission Files:**
- `index.html` - Portfolio page with semantic HTML
- `style.css` - Styling with modern CSS
- `script.js` - Interactive features with event listeners

**Tests:**
- HTML structure validation (tags, semantic elements)
- CSS class and property checks
- JavaScript feature detection
- Console error checking

**Expected Score:** ~95-100% (all tests should pass)

**Usage:**
```bash
python test_api_requests.py --test web
```

---

### 2. API Testing Template (`api`)

**Description:** Tests a Node.js Express REST API with multiple endpoints.

**Submission Files:**
- `server.js` - Express server with REST endpoints
- `package.json` - NPM dependencies

**Configuration:**
- `setup.json` - Docker container (node:18-alpine)

**Tests:**
- Health check endpoint (`/health`)
- JSON response validation (`/api/users`, `/api/user/:id`)
- POST request handling

**Expected Score:** ~90-100% (requires Docker)

**Usage:**
```bash
python test_api_requests.py --test api
```

---

### 3. Input/Output Template (`io`)

**Description:** Tests a Python command-line calculator program.

**Submission Files:**
- `calculator.py` - Calculator with stdin/stdout
- `requirements.txt` - Python dependencies (none)

**Configuration:**
- `setup.json` - Docker container (python:3.11-slim)

**Tests:**
- Addition operation
- Subtraction operation
- Multiplication operation
- Division operation
- Edge cases (zero handling)

**Expected Score:** ~85-100% (depends on implementation)

**Usage:**
```bash
python test_api_requests.py --test io
```

---

### 4. Custom Template (`custom`)

**Description:** Tests a custom grading template with file and function checks.

**Submission Files:**
- `main.py` - Python file with functions

**Configuration:**
- `custom_template.py` - Custom template implementation

**Tests:**
- File existence check
- Function definition check

**Expected Score:** 100% (simple checks)

**Usage:**
```bash
python test_api_requests.py --test custom
```

## 📊 API Endpoints

### POST `/grade_submission/`

**Purpose:** Grade a student submission with specified template

**Request Type:** `multipart/form-data`

**Required Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `submission_files` | File[] | Student code files |
| `template_preset` | String | "web dev", "api", "io", or "custom" |
| `student_name` | String | Student's name |
| `student_credentials` | String | Authentication token |
| `include_feedback` | Boolean | Include detailed feedback |
| `criteria_json` | File | Grading criteria JSON |

**Optional Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `feedback_json` | File | Feedback configuration |
| `setup_json` | File | Docker setup (required for api/io) |
| `custom_template` | File | Custom template (required for custom) |
| `feedback_type` | String | "default" or "ai" |
| `openai_key` | String | OpenAI API key (for AI feedback) |

**Response Example:**
```json
{
  "server_status": "Server connection happened successfully",
  "autograding_status": "completed",
  "final_score": 92.5,
  "feedback": "Great work! Minor improvements needed in...",
  "test_report": [
    {
      "name": "has_tag",
      "score": 100,
      "report": "Found 5 of 5 required div tags",
      "parameters": {"tag": "div", "required_count": 5}
    },
    {
      "name": "has_class",
      "score": 85,
      "report": "Found 8 of 10 required CSS classes",
      "parameters": {"class_names": ["container", "row"], "required_count": 10}
    }
  ]
}
```

### GET `/template/{template_name}`

**Purpose:** Get template metadata and available tests

**Parameters:**
- `template_name`: "web_dev", "api", "io", or "essay"

**Response Example:**
```json
{
  "template_name": "Web Development",
  "template_description": "Template for grading web development assignments",
  "tests": [
    {
      "name": "has_tag",
      "description": "Checks for HTML tags",
      "required_file": "HTML",
      "parameters": [
        {"name": "tag", "description": "HTML tag name", "type": "string"},
        {"name": "required_count", "description": "Minimum occurrences", "type": "integer"}
      ]
    }
  ]
}
```

## 🔧 Configuration Files

### criteria.json Structure

```json
{
  "base": {
    "weight": 100,
    "subjects": {
      "subject_name": {
        "weight": 50,
        "tests": [
          {
            "name": "test_function_name",
            "file": "filename.ext",
            "calls": [
              ["param1", "param2"],
              ["param1", "param2"]
            ]
          }
        ]
      }
    }
  }
}
```

**Key Points:**
- `weight`: Relative importance (sums to 100)
- `subjects`: Logical grouping of tests
- `tests`: Array of test configurations
- `calls`: Array of parameter sets for each test execution

### feedback.json Structure

```json
{
  "general": {
    "report_title": "Assignment Feedback",
    "show_passed_tests": true,
    "show_test_details": true
  },
  "default": {
    "category_headers": {
      "base": "Core Requirements",
      "subject_name": "Custom Header"
    }
  }
}
```

### setup.json Structure (for api/io templates)

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

**Key Points:**
- `runtime_image`: Docker image to use
- `container_port`: Port inside container
- `start_command`: Command to start the application
- `commands`: Setup commands (install dependencies, compile, etc.)

## 🧪 Testing Best Practices

### 1. Start API Server

```bash
cd autograder/connectors/adapters/api
python api_entrypoint.py
```

### 2. Verify Server is Running

```bash
curl http://localhost:8001/template/web_dev
```

### 3. Run Tests

```bash
# Single test
python test_api_requests.py --test web

# All tests
python test_api_requests.py --test all
```

### 4. Interpret Results

- **Score 100**: Perfect - all tests passed
- **Score 0-99**: Partial - some tests failed
- **Score 0**: Failed - needs major revisions

## 🐛 Troubleshooting

### Connection Refused
```
❌ ERROR: Could not connect to API at http://localhost:8001
```
**Solution:** Start the API server (see step 1 above)

### File Not Found
```
FileNotFoundError: Test directory not found
```
**Solution:** Run script from project root:
```bash
cd /home/raspiestchip/Desktop/AUTOGRADER/grader-builder/autograder
python test_api_requests.py
```

### Docker Errors
```
Container failed to start
```
**Solution:** 
- Ensure Docker is running: `docker ps`
- Check Docker permissions: `docker run hello-world`
- Verify image availability: `docker pull node:18-alpine`

### Timeout Errors
```
❌ ERROR: Request timed out
```
**Solution:**
- Increase timeout in script (default: 120s)
- Check system resources
- Verify Docker container is running properly

## 🚀 AWS Lambda Deployment

For AWS Lambda, modify payloads to use base64 encoding:

```python
import base64

# Read file and encode
with open('index.html', 'rb') as f:
    encoded = base64.b64encode(f.read()).decode('utf-8')

# Lambda event format
event = {
    "template_preset": "web dev",
    "student_name": "John Doe",
    "submission_files": [
        {
            "filename": "index.html",
            "content": encoded  # base64 string
        }
    ],
    "criteria": { /* criteria object */ },
    "feedback": { /* feedback object */ }
}
```

**Lambda Configuration:**
- Timeout: 5+ minutes
- Memory: 2048+ MB
- Docker support required (Lambda container image or ECS)

## 📚 Additional Resources

- **Full Documentation:** `tests/data/README.md`
- **API Reference:** Check autograder docs
- **Template Guide:** See template library documentation
- **Configuration Rules:** Refer to configuration documentation

## 💡 Tips for Creating Custom Test Data

1. **Follow Template Structure:** Match the expected format for each template type
2. **Use Realistic Data:** Create actual student submissions, not mock data
3. **Test Edge Cases:** Include both passing and failing scenarios
4. **Validate JSON:** Use `jq` or JSON validators to check syntax
5. **Document Parameters:** Add comments explaining test parameters

## 🤝 Contributing

To add new test scenarios:

1. Create directory under `tests/data/`
2. Add submission files and configurations
3. Update `test_api_requests.py` with new test method
4. Update this documentation
5. Add to curl script and Postman collection

## ✅ Verification Checklist

Before deploying to production:

- [ ] All test scenarios pass locally
- [ ] API server starts without errors
- [ ] Docker containers can be created
- [ ] File uploads work correctly
- [ ] JSON configurations are valid
- [ ] Response format matches expected structure
- [ ] Error handling works properly
- [ ] Timeout settings are appropriate
- [ ] Authentication/credentials work
- [ ] Feedback generation works

## 📞 Support

If you encounter issues:

1. Check this documentation
2. Review error messages carefully
3. Verify all prerequisites are met
4. Check Docker and API logs
5. Test with minimal payload first

---

**Created:** 2024  
**Author:** Autograder Development Team  
**Version:** 1.0.0
