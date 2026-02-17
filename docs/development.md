# Development Guide

This guide covers everything you need to know to contribute to the Autograder project.

## Table of Contents

- [Getting Started](#getting-started)
- [Project Structure](#project-structure)
- [Development Setup](#development-setup)
- [Running Tests](#running-tests)
- [Adding Features](#adding-features)
- [Code Style](#code-style)
- [Contributing](#contributing)

## Getting Started

### Prerequisites

- **Python 3.9+**: Core runtime
- **Docker & Docker Compose**: For sandbox environments
- **PostgreSQL**: For web API database (optional)
- **Git**: Version control

### Clone and Install

```bash
# Clone repository
git clone https://github.com/yourusername/autograder.git
cd autograder

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install dev dependencies
pip install pytest pytest-cov black ruff mypy
```

### Build Sandbox Images

```bash
make build-sandboxes
```

This builds Docker images for each supported language (Python, Java, JavaScript, C++).

## Project Structure

```
autograder/
├── autograder/              # Core grading logic
│   ├── models/             # Data models
│   │   ├── abstract/       # Abstract base classes
│   │   ├── config/         # Configuration models
│   │   ├── dataclass/      # Data classes
│   │   ├── criteria_tree.py
│   │   ├── result_tree.py
│   │   └── pipeline_execution.py
│   ├── services/           # Business logic
│   │   ├── grader_service.py       # Main grading engine
│   │   ├── focus_service.py        # Focus-based feedback
│   │   ├── criteria_tree_service.py # Tree construction
│   │   └── template_library_service.py
│   ├── steps/              # Pipeline steps
│   │   ├── load_template_step.py
│   │   ├── build_tree_step.py
│   │   ├── pre_flight_step.py
│   │   ├── grade_step.py
│   │   ├── focus_step.py
│   │   ├── feedback_step.py
│   │   └── export_step.py
│   ├── template_library/   # Built-in templates
│   │   ├── input_output.py
│   │   ├── api_testing.py
│   │   ├── web_dev.py
│   │   └── custom.py
│   └── utils/              # Utilities
│       ├── executors/      # Code execution helpers
│       ├── formatters/     # Output formatting
│       └── printers/       # Console output
├── sandbox_manager/         # Sandbox management
│   ├── images/             # Dockerfiles for each language
│   ├── models/             # Sandbox models
│   ├── manager.py          # Global manager
│   ├── language_pool.py    # Language-specific pools
│   └── sandbox_container.py # Container wrapper
├── web/                     # FastAPI web service
│   ├── database/           # Database models
│   ├── repositories/       # Data access layer
│   ├── schemas/            # API schemas
│   ├── services/           # Web services
│   └── main.py             # FastAPI app
├── github_action/           # GitHub Action integration
├── tests/                   # Test suite
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   └── assets/             # Test fixtures
└── docs/                    # Documentation
```

## Development Setup

### Environment Variables

Create a `.env` file in the project root:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/autograder

# OpenAI (for AI feedback mode)
OPENAI_API_KEY=your_openai_key_here

# Upstash Redis (optional, for distributed caching)
UPSTASH_REDIS_URL=your_redis_url
UPSTASH_REDIS_TOKEN=your_redis_token

# Sandbox Configuration
SANDBOX_TIMEOUT=120
SANDBOX_MEMORY_LIMIT=512m
```

### Database Setup (for Web API)

```bash
# Start PostgreSQL
docker-compose up -d postgres

# Run migrations
alembic upgrade head

# Create test data (optional)
python -m web.scripts.seed_data
```

### Start Development Server

```bash
# Start sandbox manager
docker-compose up -d

# Start FastAPI server
uvicorn web.main:app --reload --port 8000
```

Access API docs at: http://localhost:8000/docs

## Running Tests

### All Tests

```bash
pytest
```

### Specific Test Categories

```bash
# Unit tests only
pytest tests/unit/

# Integration tests only
pytest tests/integration/

# Specific test file
pytest tests/unit/test_grader_service.py

# Specific test function
pytest tests/unit/test_grader_service.py::test_grade_simple_submission
```

### With Coverage

```bash
# Generate coverage report
pytest --cov=autograder --cov=sandbox_manager --cov=web tests/

# Generate HTML coverage report
pytest --cov=autograder --cov-report=html tests/
# Open htmlcov/index.html in browser
```

### Watch Mode

```bash
# Install pytest-watch
pip install pytest-watch

# Run tests on file changes
ptw
```

## Adding Features

### Adding a New Template

1. **Create template file** in `autograder/template_library/`:

```python
# autograder/template_library/my_template.py
from autograder.models.abstract.template import Template
from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.test_result import TestResult

class MyTestFunction(TestFunction):
    @property
    def name(self) -> str:
        return "my_test"
    
    def execute(self, files: dict, sandbox, **kwargs) -> TestResult:
        # Your test logic here
        score = 100  # 0-100
        report = "Test passed!"
        
        return TestResult(
            test_name=self.name,
            score=score,
            report=report,
            passed=score >= 70
        )

class MyTemplate(Template):
    def __init__(self):
        self.tests = [MyTestFunction()]
    
    @property
    def name(self) -> str:
        return "my_template"
    
    @property
    def requires_sandbox(self) -> bool:
        return True  # If code execution needed
    
    @property
    def supported_languages(self) -> list[str]:
        return ["python", "javascript"]
```

2. **Register template** in `TemplateLibraryService`:

```python
# autograder/services/template_library_service.py
from autograder.template_library.my_template import MyTemplate

class TemplateLibraryService:
    def __init__(self):
        self.templates = {
            # ...existing templates...
            "my_template": MyTemplate(),
        }
```

3. **Write tests**:

```python
# tests/unit/test_my_template.py
from autograder.template_library.my_template import MyTestFunction

def test_my_test_function():
    test_func = MyTestFunction()
    result = test_func.execute(files={}, sandbox=None)
    
    assert result.score >= 0
    assert result.report is not None
```

### Adding a New Pipeline Step

1. **Create step file** in `autograder/steps/`:

```python
# autograder/steps/my_step.py
from autograder.models.abstract.pipeline_step import PipelineStep
from autograder.models.pipeline_execution import PipelineExecution

class MyStep(PipelineStep):
    @property
    def name(self) -> str:
        return "my_step"
    
    def execute(self, execution: PipelineExecution) -> PipelineExecution:
        # Your step logic here
        print(f"Executing {self.name}")
        
        # Modify execution as needed
        execution.metadata["my_step_completed"] = True
        
        return execution
```

2. **Add to pipeline** in `autograder.py`:

```python
# autograder/autograder.py
from autograder.steps.my_step import MyStep

def build_pipeline(...):
    steps = [
        LoadTemplateStep(),
        BuildTreeStep(),
        PreFlightStep(),
        GradeStep(),
        MyStep(),  # Add your step
        FocusStep(),
        FeedbackStep(),
    ]
    return AutograderPipeline(steps)
```

### Adding a New API Endpoint

1. **Create route** in `web/`:

```python
# web/routes/my_routes.py
from fastapi import APIRouter, Depends
from web.schemas.my_schema import MyRequest, MyResponse
from web.services.my_service import MyService

router = APIRouter(prefix="/api/v1/my-endpoint", tags=["my-endpoint"])

@router.post("/", response_model=MyResponse)
async def create_something(
    request: MyRequest,
    service: MyService = Depends()
):
    result = await service.create(request)
    return result
```

2. **Create schema** in `web/schemas/`:

```python
# web/schemas/my_schema.py
from pydantic import BaseModel

class MyRequest(BaseModel):
    name: str
    value: int

class MyResponse(BaseModel):
    id: int
    name: str
    value: int
```

3. **Register route** in `web/main.py`:

```python
# web/main.py
from web.routes import my_routes

app.include_router(my_routes.router)
```

## Code Style

### Python Style Guide

We follow PEP 8 with some modifications:

- **Line length**: 100 characters
- **Quotes**: Double quotes for strings
- **Type hints**: Required for all functions
- **Docstrings**: Google style

### Formatting

Use Black for automatic formatting:

```bash
# Format all files
black autograder/ sandbox_manager/ web/ tests/

# Check formatting without changes
black --check autograder/
```

### Linting

Use Ruff for fast linting:

```bash
# Lint all files
ruff check autograder/ sandbox_manager/ web/ tests/

# Auto-fix issues
ruff check --fix autograder/
```

### Type Checking

Use mypy for type checking:

```bash
# Type check all files
mypy autograder/ sandbox_manager/ web/

# Ignore specific errors
mypy --ignore-missing-imports autograder/
```

### Pre-commit Hooks

Install pre-commit hooks:

```bash
# Install pre-commit
pip install pre-commit

# Install hooks
pre-commit install

# Run manually
pre-commit run --all-files
```

`.pre-commit-config.yaml`:
```yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
  
  - repo: https://github.com/charliermarsh/ruff-pre-commit
    rev: v0.0.270
    hooks:
      - id: ruff
        args: [--fix]
  
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.3.0
    hooks:
      - id: mypy
```

## Contributing

### Contribution Workflow

1. **Fork the repository**
2. **Create a feature branch**:
   ```bash
   git checkout -b feature/my-amazing-feature
   ```
3. **Make your changes**
4. **Write tests**
5. **Run tests and linting**:
   ```bash
   pytest
   black autograder/
   ruff check autograder/
   ```
6. **Commit with meaningful message**:
   ```bash
   git commit -m "feat: add amazing feature"
   ```
7. **Push to your fork**:
   ```bash
   git push origin feature/my-amazing-feature
   ```
8. **Open a Pull Request**

### Commit Message Convention

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `style:` Code style changes (formatting)
- `refactor:` Code refactoring
- `test:` Adding tests
- `chore:` Build process or tooling changes

Examples:
```
feat: add support for Ruby sandbox
fix: resolve timeout issue in sandbox manager
docs: update API documentation
test: add integration tests for grading pipeline
```

### Pull Request Guidelines

- **Title**: Clear and descriptive
- **Description**: Explain what and why
- **Tests**: Include tests for new features
- **Documentation**: Update docs if needed
- **Small PRs**: Keep changes focused

### Code Review Process

1. Automated checks must pass (tests, linting)
2. At least one maintainer approval required
3. Address review comments
4. Squash commits if needed
5. Merge when approved

## Debugging

### Debug Pipeline Execution

```python
# Add debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Run pipeline with debug mode
pipeline = build_pipeline(...)
result = pipeline.run(submission, debug=True)
```

### Debug Sandbox Issues

```bash
# Check running containers
docker ps

# View container logs
docker logs <container_id>

# Execute commands in container
docker exec -it <container_id> bash

# Check sandbox manager status
python -c "
from sandbox_manager.manager import SandboxManager
manager = SandboxManager.get_instance()
print(manager.get_status())
"
```

### Debug Database Issues

```bash
# Connect to database
docker-compose exec postgres psql -U autograder

# View tables
\dt

# Query submissions
SELECT * FROM submissions ORDER BY created_at DESC LIMIT 10;
```

## Performance Tips

### Optimize Sandbox Pools

```yaml
# sandbox_config.yml
pools:
  - language: python
    pool_size: 5          # Increase for high load
    scale_limit: 20       # Maximum containers
    idle_timeout: 300     # Keep warm longer
```

### Profile Code

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Your code here
pipeline.run(submission)

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumtime')
stats.print_stats(20)
```

### Database Query Optimization

```python
# Use eager loading
submissions = db.query(Submission)\
    .options(joinedload(Submission.results))\
    .all()

# Add indexes
class Submission(Base):
    __tablename__ = "submissions"
    __table_args__ = (
        Index('idx_assignment_username', 'assignment_id', 'username'),
    )
```

## Troubleshooting

### Common Issues

**Issue**: Sandbox containers won't start
```bash
# Check Docker
docker info

# Rebuild images
make build-sandboxes

# Check logs
docker-compose logs
```

**Issue**: Tests failing
```bash
# Clear pytest cache
pytest --cache-clear

# Run single test with verbose output
pytest -vv tests/unit/test_grader_service.py::test_specific_test
```

**Issue**: Import errors
```bash
# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Check Python path
python -c "import sys; print('\n'.join(sys.path))"
```

## Resources

- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **Docker Documentation**: https://docs.docker.com/
- **Pydantic Documentation**: https://docs.pydantic.dev/
- **Pytest Documentation**: https://docs.pytest.org/

## Getting Help

- **GitHub Issues**: Report bugs or request features
- **GitHub Discussions**: Ask questions or share ideas
- **Code Review**: Request help in pull requests
- **Documentation**: Check docs/ folder for detailed guides

