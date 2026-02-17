# Autograder Test Assets

This directory contains test data and documentation for the Autograder system. After the architecture refactoring to use the pipeline pattern, these assets are used for testing the new implementation.

## 📁 Directory Structure

```
tests/assets/
├── web_dev/              # Web Development template test data
│   ├── index.html        # Sample HTML submission
│   ├── style.css         # Sample CSS submission
│   ├── script.js         # Sample JavaScript submission
│   ├── criteria.json     # Grading criteria configuration
│   └── feedback.json     # Feedback configuration
│
├── api_testing/          # API Testing template test data
│   ├── server.js         # Sample Node.js API server
│   ├── package.json      # NPM dependencies
│   ├── criteria.json     # API testing criteria
│   ├── feedback.json     # Feedback configuration
│   └── setup.json        # Container setup (runtime, commands)
│
├── input_output/         # Input/Output template test data
│   ├── testing_dashboard.html  # Interactive testing web UI
│   ├── serve_dashboard.py      # Dashboard server script
│   ├── criteria_examples/      # 5 criteria tree variations
│   ├── code_examples/          # Sample code (Python, Java, JS, C++)
│   ├── calculator.py     # Sample Python program
│   ├── requirements.txt  # Python dependencies
│   ├── criteria.json     # I/O testing criteria
│   ├── feedback.json     # Feedback configuration
│   └── setup.json        # Container setup
│
├── essay/                # Essay template test data
│   ├── essay.txt         # Sample essay text
│   ├── criteria.json     # Essay grading criteria
│   └── feedback.json     # Feedback configuration
│
└── custom_template/      # Custom Template test data
    ├── main.py           # Sample Python submission
    ├── custom_template.py # Custom grading template
    ├── criteria.json     # Custom criteria
    └── feedback.json     # Feedback configuration
```

## 🚀 Quick Start

### Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt

# Ensure Docker is running (for I/O and API templates)
docker --version
```

### Running Playroom Scripts

Playroom scripts are interactive test scripts that demonstrate how to use each template with the new pipeline architecture.

**Run Individual Playroom:**
```bash
# Web Development template (no Docker needed)
python tests/playroom/webdev_playroom.py

# API Testing template (requires Docker)
python tests/playroom/api_playroom.py

# Input/Output template (requires Docker)
python tests/playroom/io_playroom.py

# Essay template (requires OpenAI API key)
export OPENAI_API_KEY='your-key-here'
python tests/playroom/essay_playroom.py
```

**Run All Playrooms:**
```bash
python tests/playroom/run_all_playrooms.py
```

**Validate Assets:**
```bash
python tests/validate_assets.py
```

## 📋 New Pipeline Architecture

The autograder has been refactored to use a pipeline pattern. Here's how to use it:

### 1. Building a Pipeline

```python
from autograder.autograder import build_pipeline
from autograder.models.dataclass.submission import Submission, SubmissionFile
from sandbox_manager.models.sandbox_models import Language

# Build pipeline (stateless, reusable)
pipeline = build_pipeline(
    template_name="webdev",           # Template name (lowercase)
    include_feedback=True,            # Boolean flag
    grading_criteria=criteria_dict,   # Dictionary with criteria structure
    feedback_config=feedback_dict,    # Optional feedback config dict
    setup_config={},                  # Empty dict or with required_files
    custom_template=None,             # Custom template object (optional)
    feedback_mode="default",          # "default" or "ai"
    export_results=False              # Boolean flag
)
```

### 2. Creating a Submission

```python
# Create submission files using SubmissionFile dataclass
submission_files = {
    "index.html": SubmissionFile(
        filename="index.html",
        content="<html>...</html>"
    ),
    "style.css": SubmissionFile(
        filename="style.css",
        content="body { margin: 0; }"
    )
}

# Create submission
submission = Submission(
    username="john.doe",
    user_id="student123",
    assignment_id=1,
    submission_files=submission_files,
    language=None  # Only needed for I/O and API templates
)
```

### 3. Running the Pipeline

```python
# Execute pipeline
pipeline_execution = pipeline.run(submission)

# Access results
status = pipeline_execution.status  # PipelineStatus enum
result = pipeline_execution.result  # GradingResult object

if result:
    print(f"Score: {result.final_score}")
    print(f"Feedback: {result.feedback}")
    print(f"Result Tree: {result.result_tree}")
```

## 📦 Template Examples

### Web Development Template

**Template Name:** `"webdev"`  
**Files:** HTML, CSS, JavaScript  
**Language:** Not required  
**Setup Config:** Empty dict `{}`

```python
pipeline = build_pipeline(
    template_name="webdev",
    include_feedback=True,
    grading_criteria={
        "base": {
            "weight": 100,
            "subjects": {
                "HTML Structure": {
                    "weight": 50,
                    "tests": [
                        {
                            "file": "index.html",
                            "name": "Check Bootstrap Linked"
                        }
                    ]
                }
            }
        }
    },
    feedback_config=None,
    setup_config={}
)

submission = Submission(
    username="student",
    user_id="123",
    assignment_id=1,
    submission_files={
        "index.html": SubmissionFile("index.html", html_content)
    },
    language=None
)
```

### API Testing Template

**Template Name:** `"api"`  
**Files:** server.js, package.json  
**Language:** `Language.NODE`  
**Setup Config:** Required with runtime configuration

```python
from sandbox_manager.models.sandbox_models import Language
from sandbox_manager.manager import initialize_sandbox_manager
from sandbox_manager.models.pool_config import SandboxPoolConfig

# Initialize sandbox manager first
pool_configs = SandboxPoolConfig.load_from_yaml("sandbox_config.yml")
manager = initialize_sandbox_manager(pool_configs)

pipeline = build_pipeline(
    template_name="api",
    include_feedback=True,
    grading_criteria=criteria_dict,
    feedback_config=None,
    setup_config={
        "runtime_image": "node:18-alpine",
        "container_port": 5000,
        "start_command": "node server.js",
        "commands": {
            "install_dependencies": "npm install"
        }
    }
)

submission = Submission(
    username="student",
    user_id="456",
    assignment_id=2,
    submission_files={
        "server.js": SubmissionFile("server.js", code),
        "package.json": SubmissionFile("package.json", pkg)
    },
    language=Language.NODE  # Required for API template
)

# Don't forget to cleanup
manager.shutdown()
```

### Input/Output Template

**Template Name:** `"IO"` (uppercase)  
**Files:** Python/Java/C++ program  
**Language:** Required - `Language.PYTHON`, `Language.JAVA`, `Language.CPP`  
**Setup Config:** Required with `required_files`

```python
from sandbox_manager.models.sandbox_models import Language

pipeline = build_pipeline(
    template_name="IO",
    include_feedback=True,
    grading_criteria={
        "base": {
            "weight": 100,
            "subjects": [
                {
                    "subject_name": "Tests",
                    "weight": 100,
                    "tests": [
                        {
                            "name": "expect_output",
                            "parameters": [
                                {"name": "inputs", "value": ["5", "3"]},
                                {"name": "expected_output", "value": "8"},
                                {"name": "program_command", "value": "python3 calc.py"}
                            ]
                        }
                    ]
                }
            ]
        }
    },
    setup_config={"required_files": ["calc.py"]}
)

submission = Submission(
    username="student",
    user_id="789",
    assignment_id=3,
    submission_files={
        "calc.py": SubmissionFile("calc.py", python_code)
    },
    language=Language.PYTHON  # Required for I/O template
)
```

### Essay Template

**Template Name:** `"essay"`  
**Files:** Text essay  
**Language:** Not required  
**Setup Config:** Empty dict `{}`

```python
pipeline = build_pipeline(
    template_name="essay",
    include_feedback=True,
    grading_criteria={
        "base": {
            "weight": 100,
            "subjects": {
                "Content": {
                    "weight": 100,
                    "tests": [
                        {
                            "file": "essay.txt",
                            "name": "Grammar and Spelling"
                        }
                    ]
                }
            }
        }
    },
    feedback_mode="ai"  # Requires OPENAI_API_KEY
)

submission = Submission(
    username="student",
    user_id="999",
    assignment_id=4,
    submission_files={
        "essay.txt": SubmissionFile("essay.txt", essay_content)
    },
    language=None
)
```

## 🌐 Web API (RESTful)

The autograder now provides a RESTful API for grading submissions. The API endpoints are documented in the Web API module.

### Available Endpoints

- `GET /api/v1/health` - Health check
- `POST /api/v1/configs` - Create grading configuration
- `GET /api/v1/configs` - List configurations
- `POST /api/v1/submissions` - Submit code for grading
- `GET /api/v1/submissions/{id}` - Get submission results

### Example: Submit Code via API

```bash
# 1. Create configuration
curl -X POST http://localhost:8000/api/v1/configs \
  -H "Content-Type: application/json" \
  -d '{
    "external_assignment_id": "hw1",
    "template_name": "webdev",
    "language": null,
    "criteria_config": {
      "base": {
        "weight": 100,
        "subjects": {...}
      }
    }
  }'

# 2. Submit code
curl -X POST http://localhost:8000/api/v1/submissions \
  -H "Content-Type: application/json" \
  -d '{
    "external_assignment_id": "hw1",
    "external_user_id": "student123",
    "username": "john.doe",
    "files": {
      "index.html": "<html>...</html>"
    }
  }'

# 3. Get results
curl http://localhost:8000/api/v1/submissions/1
```

## 🔑 Important Changes from Old Architecture

### Breaking Changes

1. **Removed Components:**
   - ❌ `autograder_facade.py` - No longer exists
   - ❌ `Autograder.grade()` - No longer available
   - ❌ `AutograderRequest` class - Removed
   - ❌ `AssignmentConfig` class - Removed

2. **New Components:**
   - ✅ `build_pipeline()` - Creates pipeline
   - ✅ `Submission` - New submission format
   - ✅ `SubmissionFile` - File wrapper dataclass
   - ✅ `PipelineExecution` - Result object

3. **Submission Format:**
   ```python
   # ❌ Old (no longer works)
   submission_files = {
       "file.py": "print('hello')"
   }
   
   # ✅ New (required)
   submission_files = {
       "file.py": SubmissionFile("file.py", "print('hello')")
   }
   ```

4. **Template Names:**
   - `"webdev"` (lowercase, not "web dev")
   - `"api"` (lowercase, not "api_testing")
   - `"IO"` (uppercase for I/O)
   - `"essay"` (lowercase)

5. **Language Specification:**
   - Required for I/O: `Language.PYTHON`, `Language.JAVA`, `Language.CPP`
   - Required for API: `Language.NODE`
   - Not needed for webdev and essay

## 🧪 Testing

### Run Integration Tests

```bash
pytest tests/integration/ -v
```

### Run Web API Tests

```bash
pytest tests/web/ -v
```

### Run Playroom Suite

```bash
python tests/playroom/run_all_playrooms.py
```

### Validate Assets

```bash
python tests/validate_assets.py
```

## 📝 Notes

- All test data is realistic and follows best practices
- Playroom scripts demonstrate correct usage of new architecture
- Tests are designed to pass with provided submissions
- Modify criteria.json files to test different scenarios
- Use setup.json for templates requiring runtime environments (I/O, API)
- Sandbox manager is initialized automatically by pipeline when needed

## 🔧 Troubleshooting

### Import Errors
```
ModuleNotFoundError: No module named 'connectors.models.autograder_request'
```
**Solution:** Update to new imports:
```python
from autograder.autograder import build_pipeline
from autograder.models.dataclass.submission import Submission, SubmissionFile
```

### Sandbox Errors
```
ValueError: SandboxManager has not been initialized
```
**Solution:** Initialize sandbox manager for I/O and API templates:
```python
from sandbox_manager.manager import initialize_sandbox_manager
from sandbox_manager.models.pool_config import SandboxPoolConfig

pool_configs = SandboxPoolConfig.load_from_yaml("sandbox_config.yml")
manager = initialize_sandbox_manager(pool_configs)
```

### Docker Errors
```
Error: Docker daemon is not running
```
**Solution:** Start Docker daemon:
```bash
# macOS
open -a Docker

# Linux
sudo systemctl start docker
```

## 📚 Additional Resources

- [Pipeline Integration Tests](../../tests/integration/test_pipeline_sandbox_integration.py) - Complete examples
- [Web API Tests](../../tests/web/test_api_endpoints.py) - API usage examples
- [Sandbox Manager](../../sandbox_manager/manager.py) - Sandbox management
- [Pipeline Builder](../../autograder/autograder.py) - Pipeline creation

## 🤝 Contributing

To update test assets:

1. Use the new pipeline architecture format
2. Create SubmissionFile objects for all files
3. Specify language for I/O and API templates
4. Test with playroom scripts before committing
5. Run validation script to ensure compatibility

## 📊 Migration Summary

All playroom scripts have been migrated to the new architecture:
- ✅ `webdev_playroom.py` - Updated
- ✅ `api_playroom.py` - Updated  
- ✅ `io_playroom.py` - Updated
- ✅ `essay_playroom.py` - Updated
- ✅ `run_all_playrooms.py` - Implemented
- ✅ `validate_assets.py` - Created

For detailed migration information, see [ASSET_MIGRATION_SUMMARY.md](../../tests/ASSET_MIGRATION_SUMMARY.md).

