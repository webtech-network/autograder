"""A real API process backed by its own temporary database; no compose mutation."""
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
from uuid import uuid4

import pytest
import requests
from tests.sandbox_profiles import TEST_SANDBOX_CONFIG


@pytest.fixture(scope="session")
def isolated_api(tmp_path_factory):
    directory = tmp_path_factory.mktemp("autograder-e2e")
    database = directory / "api.sqlite3"
    config = directory / "sandbox.yml"
    config.write_text(TEST_SANDBOX_CONFIG)
    token = secrets.token_hex(24)
    producer_token = secrets.token_hex(24)
    env = dict(os.environ, DATABASE_URL=f"sqlite+aiosqlite:///{database}",
        AUTOGRADER_INTEGRATION_TOKEN=token, AUTOGRADER_ATTESTATION_TOKENS=f"actions={producer_token}",
        SANDBOX_MODE="local", SANDBOX_CONFIG_FILE=str(config), LOG_LEVEL="WARNING",
        APP_ENV="test", PYTHON_DOTENV_DISABLED="1", WEB_OUTCOME_RECEIPT_DIR=str(directory / "receipts"))
    # Retain the bound socket through exec, avoiding a free-port discovery race.
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    port = listener.getsockname()[1]
    url = f"http://127.0.0.1:{port}/api/v1"
    repo = Path(__file__).resolve().parents[2]
    # The API never creates tables; migrate first, exactly as a deployment does.
    migration = subprocess.run([sys.executable, "-m", "alembic", "-c", "web/alembic.ini", "upgrade", "head"],
                               cwd=repo, env=env, capture_output=True, text=True, timeout=120, check=False)
    if migration.returncode:
        pytest.fail("Migrating the isolated API database failed:\n" + migration.stderr)
    log_path = directory / "server.log"
    with log_path.open("w") as log:
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "web.main:app",
            "--fd", str(listener.fileno()), "--log-level", "warning"], cwd=repo, env=env,
            pass_fds=(listener.fileno(),), stdout=log, stderr=subprocess.STDOUT)
        listener.close()
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    pytest.fail("Isolated API exited during startup:\n" + log_path.read_text())
                try:
                    if requests.get(url + "/health", timeout=0.5).status_code == 200:
                        break
                except requests.RequestException:
                    pass
                time.sleep(0.05)
            else:
                pytest.fail("Isolated API startup timed out:\n" + log_path.read_text())
            yield {"url": url, "token": token, "producer_token": producer_token,
                   "database": database, "log": log_path}
        finally:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


@pytest.fixture
def api_base_url(isolated_api):
    return isolated_api["url"]


@pytest.fixture
def auth_headers(isolated_api):
    return {"Authorization": "Bearer " + isolated_api["token"]}


@pytest.fixture
def producer_headers(isolated_api):
    """Restricted attestation-only credential for the `actions` producer."""
    return {"Authorization": "Bearer " + isolated_api["producer_token"]}


@pytest.fixture
def run_id():
    return uuid4().hex
