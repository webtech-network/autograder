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

Who owns what, and which package may import which, is described once in
[Responsibilities and Dependencies](../architecture/overview.md). In short:

```
autograder/          core: contracts, compilation, assessment, grading, feedback
├── autograder.py         AutograderPipeline.run (the explicit run order)
├── facade.py             evaluate_submission
├── models/               contracts/ (definition, outcome, scoring, verification,
│                         catalog), abstract/ (TestFunction, Template), capabilities,
│                         execution and process protocols, language, criteria tree
├── services/             assessment, grading, preparation, file selection,
│                         feedback/focus/report, comparison, template registry
├── template_library/     built-in evaluators
└── translations/         en and pt_br messages
sandbox_manager/     container pools, leases, run_process, private control API
execution_host/      HostCapabilities composition (Docker, S3 fixtures, OpenAI)
web/                 HTTP host: configs, durable jobs, delivery, deliberate execution
github_action/       Actions host
examples/            runnable definitions and trusted Python examples
tests/               unit/, web/, integration/ (Docker), e2e/ (Docker + API process)
docs/                documentation (contracts/ are normative)
archive/             historical designs and roadmaps, not current guidance
```

## Development Setup

### Environment Variables

Create a `.env` file in the project root:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost:5432/autograder

# OpenAI (AI evaluators such as ai_sorting_algorithm)
OPENAI_API_KEY=your_openai_key_here

# Sandbox host (see docs/contracts/SANDBOX.md); images per language come
# from the runtimes: map in sandbox_config.yml
SANDBOX_MODE=local
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
# Local mode (default): the API process owns its sandbox pools directly
uvicorn web.main:app --reload --port 8000

# Remote mode: the private control API on loopback, one worker
export SANDBOX_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
python -m sandbox_manager &
SANDBOX_MODE=remote SANDBOX_API_URL=http://127.0.0.1:8001 uvicorn web.main:app --port 8000
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
pytest tests/unit/services/test_grading.py

# Specific test function
pytest tests/unit/services/test_grading.py::test_balance_nodes_only_subjects
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

### Adding an evaluator

Follow [Adding an evaluator](../architecture/extending.md): implementation,
parameter contract, registration and tests, with runnable static and execution
examples. A built-in evaluator is registered in its template under
`autograder/template_library/` (new built-in templates are added to
`autograder/services/template_library_service.py`); trusted callers pass
`templates={identifier: instance}` instead.

### Changing the run order

For cross-cutting execution changes, update the explicit call sequence in
`autograder/autograder.py`. Pass typed inputs and return values directly.
Keep required assessment failures separate from optional enrichment failures,
and close owned sessions before constructing the terminal outcome.
Do not add step registries or store intermediate artifacts in diagnostic events.
See [the grading flow](../core/pipeline-architecture.md).

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

# Check control API pools, leases and retained cleanup problems
curl -H "Authorization: Bearer $SANDBOX_API_TOKEN" http://127.0.0.1:8001/stats

# List sandbox containers by owning host
docker ps -a --filter label=autograder.sandbox.app=autograder-sandbox \
  --format '{{.Names}} {{.Label "autograder.sandbox.owner"}} {{.Status}}'
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
pytest -vv tests/unit/services/test_grading.py::test_specific_test
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

