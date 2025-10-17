# Development Branch Guide

## 🎯 Purpose of This Branch

The `development` branch is the **active development environment** where new features are built, tested, and refined before being merged into `main` (production).

---

## 🔄 Branch Strategy

### Main Branch (Production)
- **Stable, tested code only**
- **Tagged releases** (v0.1.0, v0.2.0, etc.)
- **Deployed to production** (PyPI, Docker Hub, GitHub Actions Marketplace)
- **Minimal dependencies** - only what's needed to run
- **No development tools**
- **Protected branch** - requires PR reviews

### Development Branch (This Branch)
- **Active feature development**
- **Latest features** (may be unstable)
- **All development tools** included
- **Pre-commit hooks** enforce quality
- **Integration testing** happens here
- **Direct commits allowed** for core contributors
- **Feature branches merge here first**

---

## 🌳 Workflow

```
feature/new-feature → development → main → release v1.0.0
```

1. **Create feature branch** from `development`
2. **Develop and test** in feature branch
3. **PR to development** for review
4. **Merge to development** after approval
5. **Test in development** (CI/CD runs)
6. **PR to main** when stable
7. **Tag release** from main

---

## 🛠️ What's Different in Development Branch

### Additional Files
- ✅ `requirements-dev.txt` - Development dependencies
- ✅ `.pre-commit-config.yaml` - Auto-formatting and linting
- ✅ `pyproject.toml` - Modern Python packaging
- ✅ `Makefile` - Convenient development commands
- ✅ `.devcontainer/` - VSCode DevContainer setup
- ✅ `DEV_SETUP.md` - Developer guide
- ✅ `.vscode/settings.json` - IDE configuration

### Development Tools Included
- **Testing**: pytest, pytest-cov, pytest-mock, pytest-asyncio
- **Code Quality**: black, flake8, mypy, pylint, isort
- **Pre-commit Hooks**: Automatic formatting before commits
- **Documentation**: Sphinx for doc generation
- **Debugging**: ipython, ipdb
- **Profiling**: memory-profiler, line-profiler
- **Security**: bandit, safety

### Configuration
- **Relaxed dependency versions** - easier updates
- **Debug logging** enabled
- **Verbose error messages**
- **Coverage reporting** configured
- **Auto-reload** for API development

---

## 🚀 Quick Start

### For New Contributors

1. **Clone and switch to development**
   ```bash
   git clone https://github.com/YOUR_USERNAME/autograder.git
   cd autograder
   git checkout development
   ```

2. **Run the setup script** (recommended)
   ```bash
   make dev-setup
   ```

3. **Start coding!**
   ```bash
   # Create your feature branch
   git checkout -b feature/my-awesome-feature

   # Make changes, then test
   make test

   # Format and lint
   make format
   make lint

   # Run all checks
   make all
   ```

See [DEV_SETUP.md](DEV_SETUP.md) for detailed instructions.

---

## 📋 Development Commands

All commands use the Makefile:

```bash
# Setup
make install-dev      # Install all dependencies
make setup-hooks      # Install pre-commit hooks
make dev-setup        # Complete setup

# Testing
make test             # Run all tests
make test-cov         # Run tests with coverage
make test-unit        # Run only unit tests
make test-integration # Run only integration tests

# Code Quality
make format           # Auto-format code
make lint             # Run linters
make type-check       # Run type checker
make security         # Security checks
make all              # Run everything

# Running
make run-api          # Start API server (dev mode)
make docker-build     # Build Docker image

# Documentation
make docs             # Build docs
make docs-serve       # Serve docs locally

# Cleanup
make clean            # Remove build artifacts
```

---

## 🎨 Code Standards (Enforced)

### Before Every Commit
Pre-commit hooks automatically run:
1. **Black** - Code formatting
2. **isort** - Import sorting
3. **flake8** - Linting
4. **mypy** - Type checking
5. **bandit** - Security scanning

If these fail, your commit is blocked until you fix the issues.

### Manual Checks
```bash
# Run all checks manually
make all

# Or individually
make format      # Auto-fixes formatting
make lint        # Shows linting errors
make type-check  # Shows type errors
```

---

## 🧪 Testing Requirements

### For All PRs to Development
- ✅ All tests pass
- ✅ Coverage > 80%
- ✅ No linting errors
- ✅ Type hints added
- ✅ Docstrings written

### Running Tests
```bash
# Quick test
make test-unit

# Full test with coverage
make test-cov

# Specific test
pytest tests/autograder/test_facade.py -v
```

---

## 🔀 Merging to Main

### Prerequisites
Before merging development → main:

1. ✅ All tests pass in development
2. ✅ CI/CD pipeline green
3. ✅ Code review completed
4. ✅ CHANGELOG.md updated
5. ✅ Version bumped
6. ✅ Documentation updated
7. ✅ Breaking changes documented

### Process
```bash
# From development branch
git checkout development
git pull origin development

# Create PR to main
# After approval, maintainer will:
# 1. Merge to main
# 2. Tag release
# 3. Publish to PyPI
```

---

## 📦 What Goes to Production

When merging to `main`, these files are **excluded or modified**:

### Excluded from Main
- ❌ `requirements-dev.txt` (dev dependencies)
- ❌ `.pre-commit-config.yaml` (development only)
- ❌ `.devcontainer/` (optional for contributors)
- ❌ `DEV_SETUP.md` (development guide)

### Modified for Main
- 📝 `pyproject.toml` - Only production config
- 📝 `requirements.txt` - Pinned versions
- 📝 `README.md` - User-focused, not dev-focused
- 📝 `.github/workflows/` - Production CI/CD only

---

## 🔐 Environment Variables

### Development
Use `.env` file for local development:

```bash
# Copy example and fill in
cp .env.example .env

# Edit with your keys
nano .env
```

### Production (Main Branch)
Environment variables come from:
- GitHub Secrets (for CI/CD)
- Docker environment variables
- Platform configuration (AWS, Heroku, etc.)

---

## 🐛 Debug vs Production

### Development Branch
```python
# Verbose logging
logging.basicConfig(level=logging.DEBUG)

# Detailed error messages
DEBUG = True

# Auto-reload servers
uvicorn.run(app, reload=True)

# Relaxed security for testing
CORS_ORIGINS = ["*"]
```

### Main Branch (Production)
```python
# Minimal logging
logging.basicConfig(level=logging.WARNING)

# Generic error messages
DEBUG = False

# Optimized servers
uvicorn.run(app, reload=False, workers=4)

# Strict security
CORS_ORIGINS = ["https://yourdomain.com"]
```

---

## 📊 Monitoring Development

### Check Branch Health
```bash
# Run all checks
make all

# Check coverage
make test-cov

# Check for security issues
make security
```

### Before Every PR
```bash
# Ensure your branch is clean
git status

# Update from development
git pull origin development

# Run full check
make all

# Push and create PR
git push origin feature/your-feature
```

---

## 🆘 Getting Help

- **Development questions**: GitHub Discussions
- **Bug in development**: Open an issue with `[DEV]` prefix
- **CI/CD failures**: Check Actions tab
- **Setup issues**: See DEV_SETUP.md

---

## ⚡ Tips for Efficient Development

1. **Use the Makefile** - Don't memorize commands
2. **Let pre-commit do its job** - Don't fight it
3. **Write tests first** - TDD saves time
4. **Run `make all` before pushing** - Catch issues early
5. **Use feature branches** - Keep development clean
6. **Commit often** - Small commits are easier to review
7. **Ask questions** - Use Discussions

---

## 🎯 Next Steps

1. Read [DEV_SETUP.md](DEV_SETUP.md) for detailed setup
2. Check [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines
3. Look at [good first issues](https://github.com/YOUR_ORG/autograder/labels/good%20first%20issue)
4. Join our Discord community

---

Happy developing! 🚀
