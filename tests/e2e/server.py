"""Test-only ASGI bootstrap with isolated sandbox ownership and normal lifespan."""
import os

from sandbox_manager import language_pool, manager

owner = os.environ["AUTOGRADER_E2E_OWNER"]
# Both sandbox creation and orphan discovery are scoped to this test process.
# The shared host's ordinary autograder.sandbox.app containers are never selected.
label = "autograder.e2e." + owner
language_pool.LABEL_APP = label
manager.LABEL_APP = label
# Uvicorn owns process signals; the real app lifespan shuts down this manager.
manager._register_shutdown_handlers = lambda instance: None

from web.main import app  # noqa: E402
