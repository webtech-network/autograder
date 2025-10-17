# Git Workflow for Development Branch

## 📋 Quick Reference: What to Commit

### ✅ YES - Commit These Files

All the development setup files should be committed to the `development` branch:

```bash
# Configuration files
✅ .devcontainer/devcontainer.json
✅ .devcontainer/Dockerfile.dev
✅ .pre-commit-config.yaml
✅ .vscode/settings.json          # Shared team settings
✅ pyproject.toml
✅ requirements.txt
✅ requirements-dev.txt
✅ Makefile
✅ .gitignore

# Documentation
✅ README.md
✅ CONTRIBUTING.md
✅ DEVELOPMENT.md
✅ DEV_SETUP.md
✅ SETUP_SUMMARY.md
✅ LICENSE
✅ CHANGELOG.md

# Source code
✅ autograder/
✅ connectors/
✅ tests/
✅ docs/

# CI/CD
✅ .github/workflows/
✅ action.yml
✅ Dockerfile
✅ Dockerfile.api
```

### ❌ NO - Never Commit These

These are automatically ignored by `.gitignore`:

```bash
# Environment & secrets (CRITICAL - NEVER COMMIT!)
❌ .env                    # Contains API keys, secrets
❌ .env.local
❌ *.key
❌ *.pem

# Virtual environments
❌ venv/
❌ .venv/
❌ env/

# Python artifacts
❌ __pycache__/
❌ *.pyc
❌ *.pyo
❌ .pytest_cache/

# Build artifacts
❌ dist/
❌ build/
❌ *.egg-info/

# IDE user-specific
❌ .vscode/settings.json  # Wait, this IS committed!
❌ .idea/workspace.xml
❌ .DS_Store

# Test/Coverage reports
❌ .coverage
❌ htmlcov/
❌ .mypy_cache/

# Logs
❌ *.log
❌ logs/
```

---

## 🚀 Step-by-Step: Committing Your Development Setup

### 1. Check What's New
```bash
cd /home/raspiestchip/Desktop/DACS/testing_all_services/autograder
git status
```

You should see:
```
Untracked files:
  .devcontainer/
  .pre-commit-config.yaml
  CONTRIBUTING.md
  DEVELOPMENT.md
  DEV_SETUP.md
  LICENSE
  Makefile
  pyproject.toml
  requirements-dev.txt
  SETUP_SUMMARY.md

Modified files:
  .gitignore
  .vscode/settings.json
```

### 2. Review the Files (Optional but Recommended)
```bash
# Check .gitignore changes
git diff .gitignore

# See what's in new files
ls -la .devcontainer/
cat .pre-commit-config.yaml
```

### 3. Add Files to Git
```bash
# Add everything (gitignore will handle exclusions)
git add .

# Or add specific files/folders
git add .devcontainer/
git add .pre-commit-config.yaml
git add .vscode/settings.json
git add CONTRIBUTING.md
git add DEVELOPMENT.md
git add DEV_SETUP.md
git add LICENSE
git add Makefile
git add pyproject.toml
git add requirements-dev.txt
git add SETUP_SUMMARY.md
git add .gitignore
```

### 4. Verify What Will Be Committed
```bash
git status

# Should show all the files in green (staged)
```

### 5. Commit with Descriptive Message
```bash
git commit -m "chore: setup complete development environment

- Add DevContainer configuration for easy onboarding
- Add pre-commit hooks for code quality
- Add Makefile for common dev tasks
- Add pyproject.toml for modern Python packaging
- Add comprehensive development documentation
- Update .gitignore with proper exclusions
- Add MIT License
- Add Contributing guidelines

This creates a professional development environment that makes
it easy for new contributors to get started in minutes."
```

### 6. Push to GitHub
```bash
# Push to development branch
git push origin development
```

---

## 🔍 Special Cases

### .vscode/settings.json - Should It Be Committed?

**Opinion Split in Open Source:**

#### ✅ YES, commit it (Recommended for your project)
- **Pro**: Everyone gets the same IDE configuration
- **Pro**: Auto-formatting, linting work out of the box
- **Pro**: Reduces setup friction for contributors
- **Con**: Some devs have personal VSCode preferences

**Current approach**: We commit `.vscode/settings.json` but `.gitignore` allows overriding:
```gitignore
.vscode/*                      # Ignore everything
!.vscode/settings.json         # Except shared settings
!.vscode/tasks.json           # And tasks
!.vscode/launch.json          # And launch configs
```

#### Alternative: Don't commit, provide example
```bash
# If you prefer not to force settings:
.vscode/settings.json.example  # Commit this
.vscode/settings.json          # Don't commit (in .gitignore)
```

**My recommendation**: Keep it committed. For open source projects, consistency > flexibility.

---

## 🌿 Branch-Specific Files

### Development Branch ONLY
```bash
✅ DEVELOPMENT.md          # Explains dev branch
✅ DEV_SETUP.md            # Detailed setup guide
✅ SETUP_SUMMARY.md        # Summary
✅ requirements-dev.txt    # Dev dependencies
✅ .pre-commit-config.yaml # Maybe keep in main too
```

### Main Branch (Production)
When you merge `development` → `main`, you might **exclude**:
```bash
❌ SETUP_SUMMARY.md        # Internal doc
❌ DEVELOPMENT.md          # Dev-specific
```

But **keep**:
```bash
✅ .devcontainer/          # Contributors need this
✅ .pre-commit-config.yaml # Quality standards
✅ requirements-dev.txt    # Contributors need this
✅ DEV_SETUP.md            # Contributors need this
✅ CONTRIBUTING.md         # Essential
✅ pyproject.toml          # Essential for packaging
✅ Makefile                # Helpful for contributors
```

---

## ⚠️ Critical: Never Commit Secrets

### Examples of Secrets (NEVER COMMIT!)
```bash
# API Keys
OPENAI_API_KEY=sk-proj-abc123...
GITHUB_TOKEN=ghp_abc123...

# Database credentials
DATABASE_URL=postgresql://user:password@host:5432/db

# Redis credentials
REDIS_URL=redis://...
REDIS_TOKEN=secret123

# SSH keys
id_rsa
id_rsa.pub
```

### How to Handle Secrets

1. **Use .env file** (in .gitignore)
   ```bash
   # .env (NOT committed)
   OPENAI_API_KEY=sk-real-key-here
   ```

2. **Provide .env.example** (committed)
   ```bash
   # .env.example (committed as template)
   OPENAI_API_KEY=sk-your-key-here
   REDIS_URL=redis://localhost:6379
   ```

3. **Document in README**
   ```markdown
   ## Setup
   1. Copy `.env.example` to `.env`
   2. Fill in your API keys
   3. Never commit `.env`!
   ```

---

## 🔒 If You Accidentally Commit a Secret

### Immediate Actions

1. **Change the secret immediately** (API key, password, etc.)
2. **Remove from git history** (complicated, requires force push)
   ```bash
   # Use git filter-repo or BFG Repo-Cleaner
   # Then force push (breaks history for collaborators!)
   ```

3. **Report to GitHub** if it's a GitHub token
4. **Rotate all affected credentials**

### Prevention
- Use pre-commit hooks (we have this!)
- Use git-secrets or gitleaks
- Review diffs before committing

---

## 📊 Summary

### Command Sequence for Your Files

```bash
# 1. Verify you're on development branch
git branch
# Should show: * development

# 2. Check status
git status

# 3. Add all new files (gitignore handles exclusions)
git add .

# 4. Verify what will be committed
git status

# 5. Commit
git commit -m "chore: setup complete development environment"

# 6. Push
git push origin development

# 7. Done! 🎉
```

### What GitHub Will Receive

```
Development Branch on GitHub:
├── .devcontainer/            ✅
├── .vscode/settings.json     ✅
├── .pre-commit-config.yaml   ✅
├── autograder/               ✅
├── connectors/               ✅
├── tests/                    ✅
├── docs/                     ✅
├── CONTRIBUTING.md           ✅
├── DEVELOPMENT.md            ✅
├── DEV_SETUP.md             ✅
├── LICENSE                   ✅
├── Makefile                  ✅
├── pyproject.toml           ✅
├── requirements.txt          ✅
├── requirements-dev.txt      ✅
├── SETUP_SUMMARY.md         ✅
└── .gitignore               ✅

NOT on GitHub (ignored):
├── .env                      ❌
├── venv/                     ❌
├── __pycache__/             ❌
├── .coverage                ❌
└── htmlcov/                 ❌
```

---

## ✅ Final Checklist

Before pushing:

- [ ] Review `git status` output
- [ ] Verify no `.env` file is staged
- [ ] Verify no `venv/` folder is staged
- [ ] Verify no secrets in any file
- [ ] Commit message is descriptive
- [ ] Pushed to correct branch (development)

---

**Ready to commit? Run the commands above!** 🚀
