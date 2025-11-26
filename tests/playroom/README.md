# Autograder Playrooms

Welcome to the Autograder Playrooms! This directory contains comprehensive test environments for each grading template, allowing you to fully mock and test grading operations end-to-end.

## Overview

Each playroom provides a complete grading scenario including:
- **Submission Files**: Realistic student code/content submissions
- **Setup Configuration**: Docker/sandbox environment setup when needed
- **Criteria Configuration**: Test functions and grading criteria
- **Feedback Preferences**: Customized feedback settings
- **Full Execution**: Complete autograder workflow from submission to final report

## Available Playrooms

### 1. Web Development (`webdev_playroom.py`)
Tests HTML/CSS grading capabilities with Bootstrap integration.

**Features:**
- HTML file with Bootstrap framework
- CSS class detection tests
- Bootstrap component validation
- Custom styling checks

**Run:**
```bash
python -m tests.playroom.webdev_playroom
```

**Requirements:** None (no Docker needed)

---

### 2. API Testing (`api_playroom.py`)
Tests REST API endpoint validation in a containerized environment.

**Features:**
- Flask API with multiple endpoints
- Docker containerization
- Health check testing
- GET/POST endpoint validation
- JSON response verification

**Run:**
```bash
python -m tests.playroom.api_playroom
```

**Requirements:** Docker must be running

---

### 3. Essay Grading (`essay_playroom.py`)
Tests AI-powered essay evaluation capabilities.

**Features:**
- Sample essay submission
- AI-based criteria (clarity, grammar, argument strength)
- Thesis statement evaluation
- Adherence to prompt checking

**Run:**
```bash
export OPENAI_API_KEY='your-key-here'
python -m tests.playroom.essay_playroom
```

**Requirements:** OpenAI API key set in environment

---

### 4. Input/Output (`io_playroom.py`)
Tests command-line program validation with stdin/stdout testing.

**Features:**
- Python calculator program
- Multiple input/output test cases
- Stdin input injection
- Stdout output validation
- Docker containerized execution

**Run:**
```bash
python -m tests.playroom.io_playroom
```

**Requirements:** Docker must be running

---

## Running Playrooms

### Run Individual Playroom
```bash
# Run a specific playroom
python -m tests.playroom.webdev_playroom
python -m tests.playroom.api_playroom
python -m tests.playroom.essay_playroom
python -m tests.playroom.io_playroom
```

### Run Multiple Playrooms
```bash
# Run all playrooms
python -m tests.playroom.run_all_playrooms

# Run specific playrooms
python -m tests.playroom.run_all_playrooms webdev io

# Run multiple playrooms
python -m tests.playroom.run_all_playrooms api essay
```

### List Available Playrooms
```bash
python -m tests.playroom.run_all_playrooms --list
```

## Playroom Structure

Each playroom follows a consistent structure:

```python
def create_submission():
    """Create mock submission files"""
    return {...}

def create_setup_config():
    """Create sandbox/Docker setup if needed"""
    return {...}

def create_criteria_config():
    """Define grading criteria and test functions"""
    return {...}

def create_feedback_config():
    """Configure feedback preferences"""
    return {...}

def run_[template]_playroom():
    """Execute the complete grading workflow"""
    # 1. Create submission files
    # 2. Setup configuration
    # 3. Build autograder request
    # 4. Execute grading
    # 5. Display results
```

## What Gets Tested

### For Each Playroom:
1. **File Loading**: Submission files are properly loaded
2. **Template Selection**: Correct template is initialized
3. **Criteria Building**: Criteria tree is constructed from config
4. **Test Execution**: All test functions run successfully
5. **Scoring**: Weighted scores are calculated correctly
6. **Feedback Generation**: Feedback is generated based on preferences
7. **Response Format**: Final response matches expected structure

## Customizing Playrooms

You can modify playrooms to test specific scenarios:

### Change Submission Content
```python
def create_html_submission():
    return """<html>Your custom HTML here</html>"""
```

### Modify Criteria Weights
```python
def create_criteria_config():
    return {
        "Test Name": {
            "weight": 50,  # Adjust weight
            "test": "test_function_name",
            "parameters": {...}
        }
    }
```

### Adjust Feedback Settings
```python
def create_feedback_config():
    return {
        "tone": "encouraging",  # or "professional", "constructive"
        "detail_level": "detailed",  # or "brief", "comprehensive"
        "include_suggestions": True
    }
```

## Common Issues

### Docker Not Running
**Symptoms:** API or I/O playrooms fail with connection errors

**Solution:**
```bash
# Check Docker status
docker ps

# Start Docker if needed
sudo systemctl start docker  # Linux
# or open Docker Desktop on Mac/Windows
```

### Missing OpenAI API Key
**Symptoms:** Essay playroom exits with warning

**Solution:**
```bash
export OPENAI_API_KEY='sk-your-key-here'
```

### Module Import Errors
**Symptoms:** Cannot import autograder modules

**Solution:**
```bash
# Run from project root
cd /path/to/autograder
python -m tests.playroom.webdev_playroom
```

## Development Tips

### Adding a New Playroom

1. Create a new file: `tests/playroom/my_template_playroom.py`
2. Follow the existing structure
3. Add to `run_all_playrooms.py` PLAYROOMS dict:
```python
PLAYROOMS = {
    "mytemplate": {
        "name": "My Template",
        "runner": run_mytemplate_playroom,
        "description": "Description here"
    }
}
```

### Testing Changes

Use playrooms to quickly test autograder changes:
1. Make changes to autograder code
2. Run relevant playroom
3. Check output for expected behavior

### Debugging

Add debug logging to playrooms:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Architecture

```
tests/playroom/
├── __init__.py
├── README.md                  # This file
├── webdev_playroom.py        # Web development tests
├── api_playroom.py           # API testing tests
├── essay_playroom.py         # Essay grading tests
├── io_playroom.py            # I/O testing tests
└── run_all_playrooms.py      # Runner for all playrooms
```

## Contributing

When adding new templates to the autograder:
1. Create a corresponding playroom
2. Include realistic submission examples
3. Test all template features
4. Document any special requirements
5. Add to run_all_playrooms.py

## License

Same as parent project.

## Questions?

See main project documentation or contact the maintainers.

