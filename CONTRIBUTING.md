# Contributing to Autograder

Thanks for your interest in contributing to Autograder.

We currently follow a **basic Git workflow** and coordinate work through GitHub Issues and Pull Requests.

## Before You Start

1. Read the [Code of Conduct](CODE_OF_CONDUCT.md).
2. Use the issue templates when opening new issues (`Bug report`, `Feature proposal`, `Implementation task`, `Umbrella initiative`, `Hypothesis / RFC`).
3. Check the open issues and pick one that matches your interest.
4. Comment on the issue and tag a maintainer to request context and confirm alignment before implementation.
5. Read [AGENTS.md](AGENTS.md), the [responsibility map](docs/architecture/overview.md) and, for a new evaluator, [Adding an evaluator](docs/architecture/extending.md).
6. Set up the repository as described in the [Development Guide](docs/guides/development.md#setup).

## Contribution Workflow

1. **Sync your local repository**

   ```bash
   git checkout main
   git pull origin main
   ```

2. **Create a branch**

   ```bash
   git checkout -b feat/short-description
   ```

3. **Implement the change**

   Keep changes focused on the issue scope.

4. **Run the checks CI runs**

   ```bash
   make verify              # always: lint, contracts, docs build, unit and HTTP (SQLite) tests
   make test-postgres       # changes to persistence, workers or idempotency (needs TEST_POSTGRES_URL)
   make test-integration    # changes to execution or evaluators (needs Docker)
   make test-e2e            # changes to the HTTP service (needs Docker)
   ```

   CI runs all of them on every pull request; see
   [Verification](docs/guides/development.md#verification).

5. **Commit your work**

   ```bash
   git add .
   git commit -m "feat: short summary of change"
   ```

6. **Push and open a PR**

   ```bash
   git push origin feat/short-description
   ```

   Then open a Pull Request linked to the issue.

## Pull Request Expectations

- Clearly describe **what** changed and **why**.
- Reference the issue in the PR description (for example, `Closes #123`).
- Keep PRs focused and reviewable.
- Address review feedback from maintainers.

## Review and Merge

Once your PR is open, maintainers will review it. After requested changes are addressed and approvals are in place, the PR can be merged.
