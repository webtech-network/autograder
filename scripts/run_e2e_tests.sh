#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
# The pytest fixture owns an isolated API process, temporary database, and
# task-scoped sandboxes. Shared compose services and volumes are never mutated.
# Build sandbox images first with `make sandbox-build-all` when needed.
exec python -m pytest tests/e2e/ -v "$@"
