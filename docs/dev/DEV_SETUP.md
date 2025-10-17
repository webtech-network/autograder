# Development Environment Setup Guide

This guide will help you set up your local development environment for contributing to the Autograder project.

## 🎯 Quick Start (Recommended)

### Option 1: Using VSCode DevContainer (Easiest)

If you have VSCode and Docker installed:

1. **Clone and open in VSCode**
   ```bash
   git clone https://github.com/YOUR_USERNAME/autograder.git
   cd autograder
   git checkout development
   code .
   ```

2. **Reopen in Container**
   - VSCode will prompt to "Reopen in Container"
   - Or press `F1` → "Dev Containers: Reopen in Container"
   - Everything will be set up automatically!

### Option 2: Manual Setup (Traditional)

#### Prerequisites
- Python 3.8+ (3.11 recommended)
- Git
- Virtual environment tool (venv, virtualenv, or conda)

#### Steps

1. **Clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/autograder.git
   cd autograder
   git checkout development
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv

   # On Linux/Mac:
   source venv/bin/activate

   # On Windows:
   venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   # Install production dependencies
   pip install -r requirements.txt

   # Install development dependencies
   pip install -r requirements-dev.txt
   ```

4. **Set up pre-commit hooks**
   ```bash
   pre-commit install
   ```

5. **Verify installation**
   ```bash
   make test
   ```

---

## 🛠️ Development Workflow

### Daily Development

1. **Start your day**
   ```bash
   git checkout development
   git pull origin development
   ```

2. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

3. **Make your changes**
   - Write code
   - Add tests
   - Update documentation

4. **Test as you go**
   ```bash
   # Run tests
   make test

   # Run tests with coverage
   make test-cov

   # Run only unit tests (faster)
   make test-unit
   ```

5. **Format and lint**
   ```bash
   # Format code (auto-fix)
   make format

   # Run linters
   make lint

   # Type check
   make type-check
   ```

6. **Run everything before committing**
   ```bash
   make all
   ```

### Making Commits

Pre-commit hooks will automatically:
- Format your code with Black
- Sort imports with isort
- Run flake8 linting
- Check for security issues
- Validate YAML/JSON files

If pre-commit fails, fix the issues and commit again.

```bash
git add .
git commit -m "feat(templates): add Python unit testing template"
git push origin feature/your-feature-name
```

---

## 📁 Project Structure

```
autograder/
├── autograder/              # Core autograding logic
│   ├── builder/            # Test tree construction
│   ├── core/               # Grading engine
│   └── ...
├── connectors/             # Adapters for different platforms
│   └── adapters/
│       ├── api/           # REST API adapter
│       └── github_action_adapter/  # GitHub Actions adapter
├── tests/                  # Test suite
├── docs/                   # Documentation
├── requirements.txt        # Production dependencies
├── requirements-dev.txt    # Development dependencies
├── pyproject.toml         # Project configuration
├── Makefile               # Development commands
└── .pre-commit-config.yaml # Pre-commit hooks
```

---

## 🧪 Testing

### Running Tests

```bash
# All tests
make test

# With coverage report
make test-cov

# Only unit tests (fast)
make test-unit

# Only integration tests
make test-integration

# Watch mode (reruns on file changes)
make test-watch

# Run specific test file
pytest tests/autograder/test_facade.py -v

# Run specific test
pytest tests/autograder/test_facade.py::TestAutograderFacade::test_specific -v
```

### Writing Tests

Tests live in `tests/` directory, mirroring the structure of the source code.

```python
# tests/autograder/test_example.py
import pytest
from autograder.module import function

class TestExample:
    def test_function_works(self):
        # Arrange
        input_data = "test"

        # Act
        result = function(input_data)

        # Assert
        assert result == "expected"
```

### Test Markers

```python
@pytest.mark.unit
def test_unit_test():
    pass

@pytest.mark.integration
def test_integration():
    pass

@pytest.mark.slow
def test_slow_operation():
    pass
```

---

## 🎨 Code Style

### Formatting

We use **Black** for code formatting (88 character line length):

```bash
# Auto-format all code
make format

# Check formatting without changes
make format-check
```

### Import Sorting

We use **isort** with Black profile:

```bash
# Auto-sort imports
isort autograder connectors tests
```

### Linting

We use **flake8** for linting:

```bash
# Run linter
make lint
```

### Type Hints

Use type hints for better code quality:

```python
def grade_submission(config: AssignmentConfig) -> AutograderResponse:
    """Grade a student submission."""
    pass
```

---

## 🏃 Running the Application

### API Server

```bash
# Development mode (with auto-reload)
make run-api

# Production mode
make run-api-prod

# Manual
uvicorn connectors.adapters.api.api_entrypoint:app --reload
```

API will be available at: http://localhost:8000

### Using Docker

```bash
# Build Docker image
make docker-build

# Run API in Docker
make docker-run-api
```

---

## 🔍 Debugging

### Using IPython

```bash
# Install included in requirements-dev.txt
ipython
```

### Using ipdb (Python debugger)

Add breakpoint in your code:

```python
import ipdb; ipdb.set_trace()
```

### VSCode Debugging

Launch configurations are in `.vscode/launch.json`:
- Press `F5` to start debugging
- Set breakpoints by clicking left of line numbers

---

## 📝 Documentation

### Building Docs

```bash
# Build documentation
make docs

# Serve documentation locally
make docs-serve
# Visit http://localhost:8000
```

### Writing Docstrings

Use Google-style docstrings:

```python
def function(param1: str, param2: int) -> bool:
    """
    Brief description of function.

    Longer description if needed.

    Args:
        param1: Description of param1
        param2: Description of param2

    Returns:
        Description of return value

    Raises:
        ValueError: When param1 is invalid
    """
    pass
```

---

## 🐛 Common Issues

### Pre-commit hooks failing

```bash
# Update pre-commit hooks
pre-commit autoupdate

# Run manually to see issues
pre-commit run --all-files
```

### Import errors

```bash
# Reinstall in development mode
pip install -e .
```

### Test failures

```bash
# Clear pytest cache
rm -rf .pytest_cache

# Run with verbose output
pytest -vv
```

### Docker issues

```bash
# Clean Docker cache
docker system prune -a

# Rebuild without cache
docker build --no-cache -t autograder:latest .
```

---

## 🔐 Environment Variables

For local development, create a `.env` file (never commit this!):

```bash
# .env
OPENAI_API_KEY=sk-...
REDIS_URL=redis://localhost:6379
REDIS_TOKEN=your-token
GITHUB_TOKEN=ghp_...
```

Load with python-dotenv:

```python
from dotenv import load_dotenv
load_dotenv()
```

---

## 📊 Code Quality Metrics

### Coverage Reports

After running `make test-cov`, view the HTML report:

```bash
# Open in browser
open htmlcov/index.html  # Mac
xdg-open htmlcov/index.html  # Linux
start htmlcov/index.html  # Windows
```


## ✅ Before Submitting PR

Run this checklist:

```bash
# 1. Format code
make format

# 2. Run all checks
make all

# 3. Update documentation if needed

# 4. Add yourself to CONTRIBUTORS.md

# 5. Update tests

# 6. Write clear commit messages
```

---

Happy coding! 🎉
