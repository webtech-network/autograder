# Autograder

<div align="center">

**A robust, educational-standards-driven autograding platform that transforms assignment grading into an engaging learning experience.**

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-009688.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Enabled-2496ED.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

[Features](#features) • [Architecture](#architecture) • [Quick Start](#quick-start) • [Templates](#grading-templates) • [Pipeline](#pipeline-workflow) • [API](#rest-api) • [GitHub Action](#github-action)

</div>

---

## Overview

The **Autograder** is an advanced educational platform designed to efficiently and accurately grade student submissions using actual pedagogical standards. What makes it stand out is its highly elaborated grading methodology that follows teacher-configured rubrics and generates comprehensive, student-friendly feedback reports.

### Why Autograder?

- **Teacher-Controlled Grading**: Complete control over evaluation criteria with tree-structured rubrics
- **Educational Standards**: Implements proper scoring categories (base, bonus, penalty) with weighted subjects
- **Multiple Assignment Types**: Native support for Web Development, APIs, Command-Line Programs, and Custom Templates
- **Secure Code Execution**: Isolated sandbox environments for safe remote code execution
- **Proven Engagement**: Students treat assignments as iterative learning challenges
- **High Performance**: Warm container pools and pipeline architecture enable rapid grading at scale
- **Intelligent Feedback**: Focus-based feedback generation that highlights the most impactful improvements

## The Grading Pipeline

Every submission flows through a sophisticated pipeline:

![Pipeline Diagram](docs/pipeline_diagram.png)

Each step is designed to maintain educational standards while providing maximum flexibility.

---

## Features

### For Educators

- **Flexible Grading Rubrics**: Create complex, tree-structured grading criteria with unlimited nesting
  - Base requirements, bonus points, and penalty deductions
  - Subject grouping with custom weights
  - Hierarchical test organization
  
- **One-Time Configuration**: Configure an assignment once, reuse for all submissions
  - Store grading configurations as reusable packages
  - Version control for grading criteria
  - Template library for common assignment types

- **Customizable Feedback**: Control how students receive feedback
  - Default mode: Structured reports with test results
  - AI mode: Intelligent, conversational feedback
  - Focus-based feedback highlighting high-impact improvements

### For Students

- **Detailed Reports**: Understand exactly why you received a certain score
- **Actionable Feedback**: Get specific guidance on what to improve
- **Iterative Learning**: Use feedback to improve and resubmit
- **Transparent Grading**: See the breakdown of scores across all criteria

### For Developers

- **REST API**: Modern FastAPI-based web service
- **GitHub Action**: Seamless integration with GitHub Classroom
- **Extensible Architecture**: Pipeline-based design for easy customization
- **Multiple Languages**: Python, Java, JavaScript/Node.js, C++ support
- **Custom Templates**: Upload your own grading logic for specialized contexts

---

## Architecture

The Autograder uses a **pipeline architecture** that processes submissions through choreographed steps, providing flexibility and excellent performance.

### Core Components

#### Pipeline Pattern

The system is built around **AutograderPipeline** - a stateless, reusable grading workflow.

```python
# Build a pipeline (configuration-driven)
pipeline = build_pipeline(
    template_name="input_output",
    include_feedback=True,
    grading_criteria=criteria_config,
    feedback_config=feedback_settings,
    setup_config={"required_files": ["main.py"]},
    feedback_mode="ai"
)

# Execute pipeline (reusable for any submission)
result = pipeline.run(submission)
```

#### Criteria Tree

Grading criteria are represented as a tree structure mirroring educational rubrics:

```
CriteriaTree
├── Base (weight: 100)
│   ├── Subject: Functionality (weight: 60)
│   │   ├── Test: Correct Output (weight: 100)
│   │   └── Test: Edge Cases (weight: 100)
│   └── Subject: Code Quality (weight: 40)
│       ├── Test: Proper Syntax (weight: 50)
│       └── Test: Good Practices (weight: 50)
├── Bonus (weight: 10)
│   └── Test: Extra Features
└── Penalty (weight: -20)
    └── Test: Late Submission
```

#### Sandbox Management

The **SandboxManager** provides secure, isolated execution environments:

- **Container Pooling**: Pre-started warm containers ready to execute
- **Multi-Language**: Python, Java, JavaScript, and C++ support
- **Automatic Lifecycle**: TTL management, health checks, and cleanup
- **Resource Control**: Memory limits, timeouts, and isolation

#### Template System

Templates provide test functions for different assignment contexts:

- **WebDev**: HTML, CSS, JavaScript validation
- **API Testing**: HTTP request validation
- **Input/Output**: Command-line program testing
- **Custom**: Upload your own test logic

---

## Pipeline Workflow

The pipeline executes these steps in sequence:

1. **Load Template** - Select test functions from the template library
2. **Build Tree** - Construct the grading rubric hierarchy  
3. **Pre-Flight** - Validate requirements and acquire sandbox (if needed)
4. **Grade** - Execute tests and calculate weighted scores
5. **Focus** - Identify high-impact failed tests
6. **Feedback** - Generate student-facing reports
7. **Export** - Send results to external systems (optional)

Each step receives a `PipelineExecution` object, performs its operation, and passes results to the next step.

---

## Grading Templates

### Native Templates

#### 1. Input/Output Template
Tests command-line programs by providing inputs and validating outputs.

```python
{
    "test_library": "input_output",
    "base": {
        "tests": [
            {
                "name": "expect_output",
                "parameters": {
                    "inputs": ["5", "3"],
                    "expected_output": "8",
                    "program_command": "python3 calculator.py"
                },
                "weight": 100
            }
        ]
    }
}
```

**Available Tests:**
- `expect_output`: Test program output with given inputs
- `check_exit_code`: Validate program exit codes
- `timeout_test`: Ensure programs complete within time limits

#### 2. API Testing Template
Makes HTTP requests to student APIs and validates responses.

```python
{
    "test_library": "api_testing",
    "base": {
        "tests": [
            {
                "name": "health_check",
                "parameters": {
                    "endpoint": "/api/health"
                }
            },
            {
                "name": "check_response_json",
                "parameters": {
                    "endpoint": "/api/users",
                    "expected_key": "users",
                    "expected_value": []
                }
            }
        ]
    }
}
```

**Available Tests:**
- `health_check`: Verify endpoint returns 200 OK
- `check_response_json`: Validate JSON response structure
- `check_status_code`: Test specific HTTP status codes
- `validate_headers`: Check response headers

#### 3. Web Development Template
Validates HTML, CSS, and JavaScript files.

```python
{
    "test_library": "web_dev",
    "base": {
        "subjects": [
            {
                "subject_name": "HTML Structure",
                "weight": 50,
                "tests": [
                    {
                        "name": "has_tag",
                        "parameters": {
                            "tag": "header",
                            "required_count": 1
                        }
                    }
                ]
            },
            {
                "subject_name": "CSS Styling",
                "weight": 50,
                "tests": [
                    {
                        "name": "has_class",
                        "parameters": {
                            "class_names": ["col-*", "container"],
                            "required_count": 5
                        }
                    }
                ]
            }
        ]
    }
}
```

**Available Tests:**
- `has_tag`: Check for HTML tags
- `has_class`: Validate CSS classes (with wildcard support)
- `check_bootstrap_linked`: Verify framework inclusion
- `has_attribute`: Check element attributes
- `check_css_property`: Validate CSS rules

#### 4. Custom Templates
Upload your own test functions for specialized grading contexts:

```python
from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.test_result import TestResult

class MyCustomTest(TestFunction):
    @property
    def name(self):
        return "my_custom_test"
    
    def execute(self, files, sandbox, **kwargs) -> TestResult:
        # Your custom grading logic
        score = 100 if condition else 0
        return TestResult(
            test_name=self.name,
            score=score,
            report="Test passed!" if score == 100 else "Test failed"
        )
```

---

## Quick Start

### Prerequisites

- Python 3.9+
- Docker and Docker Compose
- PostgreSQL (for web API mode)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/yourusername/autograder.git
cd autograder
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure sandbox pools** (edit `sandbox_config.yml`)
```yaml
pools:
  - language: python
    pool_size: 3
    scale_limit: 10
    idle_timeout: 300
    running_timeout: 120
  
  - language: java
    pool_size: 2
    scale_limit: 5
    idle_timeout: 300
    running_timeout: 120
```

4. **Build sandbox images**
```bash
make build-sandboxes
```

5. **Start the system**

**As a Web API:**
```bash
docker-compose up
```

**As a GitHub Action:**
See [GitHub Action](#-github-action) section.

**Standalone (Python script):**
```bash
python -m autograder.autograder
```

---

## REST API

The Autograder provides a FastAPI-based REST API for integration with learning management systems.

### Starting the API

```bash
# Development
uvicorn web.main:app --reload

# Production
docker-compose up
```

API documentation available at: `http://localhost:8000/docs`

### Core Endpoints

#### Create Grading Configuration
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

#### Submit for Grading
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

#### Get Results
```http
GET /api/v1/submissions/{submission_id}

Response:
{
  "submission_id": 1,
  "final_score": 85.5,
  "status": "completed",
  "feedback": "...",
  "result_tree": { ... }
}
```

---

## GitHub Action

Seamlessly integrate with GitHub Classroom.

### Usage

Add to your `.github/workflows/classroom.yml`:

```yaml
name: Autograding

on:
  push:
    branches: [ main ]

jobs:
  grade:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Run Autograder
        uses: your-org/autograder@v1
        with:
          template_preset: 'input_output'
          feedback-type: 'ai'
          include-feedback: 'true'
          github-token: ${{ secrets.GITHUB_TOKEN }}
          openai_key: ${{ secrets.OPENAI_API_KEY }}
```

### Configuration

**Inputs:**
- `template_preset`: Template to use (`input_output`, `api_testing`, `web_dev`, `custom`)
- `feedback-type`: `default` or `ai`
- `include-feedback`: `true` or `false`
- `custom_template`: JSON template for custom grading
- `openai_key`: Required for AI feedback mode

**Outputs:**
- `result`: Base64-encoded JSON with grading results

---

## Grading Result Structure

After grading, you receive a comprehensive `GradingResult` with:

- **Final Score**: Overall grade (0-100)
- **Feedback**: Generated student-facing feedback (if enabled)
- **Result Tree**: Detailed breakdown of all test results

### Result Tree Example

```json
{
  "final_score": 85.5,
  "root": {
    "base": {
      "name": "base",
      "score": 85.5,
      "weight": 100,
      "subjects": [
        {
          "name": "Functionality",
          "score": 90,
          "weight": 60,
          "tests": [
            {
              "name": "expect_output",
              "score": 100,
              "weight": 100,
              "report": "Test passed successfully!"
            }
          ]
        }
      ]
    }
  }
}
```

The result tree mirrors your grading criteria structure, making it easy to understand score breakdowns at every level.

---

## Configuration Examples

### Simple Assignment

```json
{
  "test_library": "input_output",
  "base": {
    "tests": [
      {
        "name": "expect_output",
        "parameters": {
          "inputs": ["Alice"],
          "expected_output": "Hello, Alice!",
          "program_command": "python3 greeting.py"
        },
        "weight": 100
      }
    ]
  }
}
```

### Complex Hierarchical Rubric

```json
{
  "test_library": "web_dev",
  "base": {
    "weight": 100,
    "subjects_weight": 100,
    "subjects": [
      {
        "subject_name": "HTML Structure",
        "weight": 40,
        "tests": [
          {
            "name": "has_tag",
            "parameters": {"tag": "header", "required_count": 1},
            "weight": 50
          },
          {
            "name": "has_tag",
            "parameters": {"tag": "footer", "required_count": 1},
            "weight": 50
          }
        ]
      },
      {
        "subject_name": "CSS Styling",
        "weight": 30,
        "tests": [
          {
            "name": "has_class",
            "parameters": {"class_names": ["container"], "required_count": 1}
          }
        ]
      },
      {
        "subject_name": "Accessibility",
        "weight": 30,
        "subjects": [
          {
            "subject_name": "ARIA Labels",
            "weight": 50,
            "tests": [
              {
                "name": "has_attribute",
                "parameters": {"tag": "button", "attribute": "aria-label"}
              }
            ]
          },
          {
            "subject_name": "Alt Text",
            "weight": 50,
            "tests": [
              {
                "name": "has_attribute",
                "parameters": {"tag": "img", "attribute": "alt"}
              }
            ]
          }
        ]
      }
    ]
  },
  "bonus": {
    "weight": 10,
    "tests": [
      {
        "name": "check_bootstrap_linked",
        "parameters": {"framework": "bootstrap"}
      }
    ]
  }
}
```

---

## Use Cases

### Educational Institutions
- **Automated Homework Grading**: Grade hundreds of submissions consistently
- **Immediate Feedback**: Students get instant results to iterate and improve
- **Scalable Assessment**: Handle courses with large enrollment
- **Fair Grading**: Eliminate human bias with standardized criteria

### Coding Bootcamps
- **Skill Assessment**: Evaluate student progress throughout the program
- **Challenge Labs**: Create engaging, game-like coding challenges
- **Portfolio Building**: Track student improvement over time

### Corporate Training
- **Technical Interviews**: Automated coding challenge grading
- **Employee Onboarding**: Assess technical skills of new hires
- **Skill Validation**: Verify competencies in specific technologies

### Research
- **Educational Research**: Study the impact of feedback on learning
- **Algorithm Analysis**: Evaluate different grading methodologies
- **Learning Analytics**: Gather data on common student mistakes

---

## Performance

The Autograder is designed for high performance:

- **Warm Containers**: Pre-started sandboxes eliminate cold-start delays
- **Async Processing**: FastAPI enables high concurrency
- **Pipeline Efficiency**: Stateless pipelines can be reused indefinitely
- **Configurable Pools**: Scale sandbox pools based on demand
- **Database Optimization**: Efficient storage of configurations and results

**Typical Performance:**
- Grade submission: 1-3 seconds (with warm sandbox)
- Cold start: 5-8 seconds (first request per language)
- Concurrent submissions: 100+ with proper pool sizing

---

## Security

### Sandbox Isolation
- Docker container isolation for all code execution
- Non-root user execution (sandbox user)
- Resource limits (CPU, memory, ulimits)
- Timeout protection
- Network isolation options

### Input Validation
- Pydantic models for all configuration
- File size limits
- Content sanitization
- SQL injection protection (ORM-based)

### Best Practices
- Never expose sandbox ports externally
- Use environment variables for secrets
- Implement rate limiting on API endpoints
- Regular security updates for base images

---

## Development

### Project Structure

```
autograder/
├── autograder/              # Core grading logic
│   ├── models/             # Data models (criteria tree, result tree)
│   ├── services/           # Business logic (grader, focus, reporter)
│   ├── steps/              # Pipeline steps
│   ├── template_library/   # Built-in grading templates
│   └── utils/              # Helper utilities
├── sandbox_manager/         # Sandbox container management
│   ├── images/             # Dockerfile for each language
│   ├── models/             # Sandbox models
│   ├── language_pool.py    # Pool management
│   ├── manager.py          # Global sandbox manager
│   └── sandbox_container.py # Container wrapper
├── web/                     # FastAPI web application
│   ├── database/           # Database models and connection
│   ├── repositories/       # Data access layer
│   ├── schemas/            # API request/response schemas
│   └── services/           # Web-specific services
├── github_action/           # GitHub Action adapter
├── tests/                   # Test suite
└── docker-compose.yml       # Docker orchestration
```

### Running Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/unit/test_grader_service.py

# With coverage
pytest --cov=autograder tests/
```

### Adding a New Template

1. Create a new template file in `autograder/template_library/`
2. Implement `TestFunction` subclasses
3. Create a `Template` class
4. Register in `TemplateLibraryService`

Example:
```python
# autograder/template_library/my_template.py
from autograder.models.abstract.template import Template
from autograder.models.abstract.test_function import TestFunction

class MyTestFunction(TestFunction):
    # Implement required methods
    pass

class MyTemplate(Template):
    def __init__(self):
        self.tests = [MyTestFunction()]
    
    # Implement required properties
    pass
```

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines
- Write tests for new features
- Follow PEP 8 style guide
- Update documentation
- Add type hints
- Use meaningful commit messages

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Contact

For questions, suggestions, or support:

- **Issues**: [GitHub Issues](https://github.com/yourusername/autograder/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/autograder/discussions)
- **Email**: autograder@example.com

---

## Acknowledgments

- Built with care for educators and students
- Powered by FastAPI, Docker, and modern Python
- Inspired by the need for fair, consistent, and engaging assessment

---

<div align="center">

**Star this repo if you find it useful!**

Made by educators, for educators

</div>

