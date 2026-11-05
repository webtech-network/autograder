#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
# The pytest fixture owns an isolated API process, temporary database, and
# task-scoped sandboxes. Shared compose services and volumes are never mutated.
# Build sandbox images first with `make sandbox-build-all` when needed.
# PYTHON is the interpreter command (`make test-e2e` passes `uv run --locked python`).
# shellcheck disable=SC2086
exec ${PYTHON:-python} -m pytest tests/e2e/ -v "$@"
