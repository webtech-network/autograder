"""The HTTP path as shipped: the Compose stack from this checkout (ENV-05, #426).

``make test-http`` builds the API, sandbox manager and runtime images from the
checkout, then this module starts two stacks of ``docker-compose.yml`` side by
side under different project names, each from empty volumes: PostgreSQL,
migrations, the S3 emulator seeded by ``storage-init``, the private sandbox
manager and the API in remote mode. Nothing is mocked. Every stack, its volumes
and its sandboxes are removed afterwards.

AUTOGRADER_IMAGE_TAG selects the image tag (default ``local``, as ``make images``
builds); STACK_PROJECT_PREFIX names the projects (default ``autograder-smoke``).
"""
# pylint: disable=missing-function-docstring
import json
import os
import secrets
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import docker
import pytest
import requests

from sandbox_manager.ownership import LABEL_OWNER_HOST
from tests.e2e.contracts import create_config, poll

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILES = (ROOT / "docker-compose.yml", Path(__file__).with_name("compose.smoke.yml"))
EXAMPLE = ROOT / "examples" / "assets" / "fixture_io"
RECEIPTS = "/app/data/unpublished-outcomes"
STARTUP_SECONDS = 300


def wait_for(condition, timeout, message):
    """Poll ``condition`` until it returns a truthy value (never a fixed sleep)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = condition()
        if value:
            return value
        time.sleep(0.5)
    raise AssertionError(f"Timed out after {timeout}s: {message}")


class Stack:
    """One Compose project of the development stack."""

    def __init__(self, prefix):
        self.project = f"{prefix}-{uuid4().hex[:8]}"
        self.token = secrets.token_urlsafe(32)
        self.environment = {**os.environ, "AUTOGRADER_INTEGRATION_TOKEN": self.token,
                            "SANDBOX_API_TOKEN": secrets.token_urlsafe(32), "AUTOGRADER_HTTP_PORT": ""}
        self.url = None

    @property
    def headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def compose(self, *arguments, check=True, timeout=STARTUP_SECONDS):
        files = [option for path in COMPOSE_FILES for option in ("-f", str(path))]
        result = subprocess.run(["docker", "compose", "-p", self.project, *files, *arguments], cwd=ROOT,
                                env=self.environment, capture_output=True, text=True, timeout=timeout, check=False)
        if check and result.returncode:
            logs = subprocess.run(["docker", "compose", "-p", self.project, *files, "logs", "--no-color",
                                   "--tail", "80"], cwd=ROOT, env=self.environment, capture_output=True,
                                  text=True, check=False).stdout
            raise AssertionError(f"docker compose {' '.join(arguments)} failed:\n{result.stderr}\n{logs}")
        return result

    def up(self):
        self.compose("up", "--detach", "--no-build", "--wait", "--wait-timeout", str(STARTUP_SECONDS))
        self.connect()

    def connect(self):
        address = self.compose("port", "api", "8000").stdout.strip()
        self.url = f"http://{address}/api/v1"
        wait_for(self.ready, STARTUP_SECONDS, f"{self.project} API ready")

    def ready(self):
        try:
            return requests.get(self.url + "/ready", timeout=5).status_code == 200
        except requests.ConnectionError:
            return False

    def sql(self, statement):
        return self.compose("exec", "-T", "postgres", "psql", "-U", "autograder", "-tAc", statement).stdout.strip()

    def receipts(self):
        """Receipt files in the API container; the directory appears with the first one."""
        listing = self.compose("exec", "-T", "api", "ls", "-1", RECEIPTS, check=False)
        return [name for name in listing.stdout.split() if name.endswith(".json")]

    def down(self):
        self.compose("down", "--volumes", "--remove-orphans", "--timeout", "60", check=False)


def fixture_submission(stack):
    config = create_config(stack.url, stack.headers, json.loads((EXAMPLE / "definition.json").read_text()))
    return {"external_assignment_id": config["external_assignment_id"], "external_user_id": "smoke-" + uuid4().hex,
            "username": "student", "files": [{"filename": "main.py", "content": (EXAMPLE / "main.py").read_text()}]}


def submit(stack, body, key):
    response = requests.post(stack.url + "/submissions", json=body, timeout=10,
                             headers={**stack.headers, "Idempotency-Key": key})
    assert response.status_code == 202, response.text
    return response.json()["id"]


def status(stack, submission_id):
    response = requests.get(f"{stack.url}/submissions/{submission_id}", headers=stack.headers, timeout=5)
    assert response.status_code == 200, response.text
    return response.json()["status"]


@pytest.fixture(scope="module")
def stacks():
    prefix = os.environ.get("STACK_PROJECT_PREFIX", "autograder-smoke")
    started = [Stack(prefix), Stack(prefix)]
    client = docker.from_env()
    try:
        with ThreadPoolExecutor(len(started)) as pool:
            list(pool.map(Stack.up, started))
        yield started
    finally:
        with ThreadPoolExecutor(len(started)) as pool:
            list(pool.map(Stack.down, started))
        leaked = [container.name for stack in started for container in client.containers.list(
            all=True, filters={"label": f"{LABEL_OWNER_HOST}={stack.project}-sandbox-manager"})]
        for name in leaked:
            client.containers.get(name).remove(force=True)
        client.close()
        assert not leaked, f"sandboxes survived their stack: {leaked}"


def test_two_stacks_side_by_side_grade_a_fixture_assignment_from_empty_volumes(stacks):
    assert len({stack.url for stack in stacks}) == len(stacks)
    for stack in stacks:
        # Empty volumes: the only configuration is the one this test creates, and no
        # outcome receipt arrives with the image (a dev checkout's data/ is not copied).
        assert stack.sql("select count(*) from grading_configurations") == "0"
        assert stack.receipts() == []
        submission_id = submit(stack, fixture_submission(stack), "smoke-" + uuid4().hex)
        details = poll(stack.url, stack.headers, submission_id, timeout=180)
        outcome = details["outcome"]
        assert outcome["status"] == "completed", outcome.get("error")
        assert outcome["score"] == 100


def test_a_retained_receipt_survives_recreating_the_api_and_publishes_without_regrading(stacks):
    stack = stacks[0]
    body, key = fixture_submission(stack), "smoke-" + uuid4().hex
    # Hold grading at sandbox acquisition, so publication can be made to fail deterministically.
    stack.compose("pause", "sandbox-manager")
    try:
        submission_id = submit(stack, body, key)
        wait_for(lambda: status(stack, submission_id) == "processing", 60, "the job to be claimed")
        stack.compose("stop", "postgres")
    finally:
        stack.compose("unpause", "sandbox-manager")
    # Grading finishes, the database is gone: the finalized outcome is kept as a receipt.
    name = wait_for(lambda: [item for item in stack.receipts() if item.startswith(f"submission-{submission_id}-")],
                    180, "the outcome receipt")[0]
    receipt = json.loads(stack.compose("exec", "-T", "api", "cat", f"{RECEIPTS}/{name}").stdout)
    assert receipt["outcome"]["status"] == "completed" and receipt["outcome"]["score"] == 100

    # Replace the API container; only the receipt volume carries the grade over.
    stack.compose("stop", "api")
    stack.compose("start", "postgres")
    wait_for(lambda: stack.compose("exec", "-T", "postgres", "pg_isready", "-U", "autograder",
                                   check=False).returncode == 0, 60, "PostgreSQL back")
    stack.compose("up", "--detach", "--no-deps", "--no-build", "--force-recreate", "api")
    stack.connect()

    details = poll(stack.url, stack.headers, submission_id, timeout=180)
    assert details["outcome"]["execution_id"] == receipt["outcome"]["execution_id"]
    assert details["outcome"]["score"] == 100
    assert stack.receipts() == []
    # One grading attempt, published from the receipt: nothing was graded again.
    assert stack.sql(f"select attempt_count from submissions where id = {int(submission_id)}") == "1"
    assert stack.sql(f"select status from grading_attempts where submission_id = {int(submission_id)}") == "published"

    # Replaying the acceptance returns the same submission and grades nothing.
    assert submit(stack, body, key) == submission_id
    assert status(stack, submission_id) == "completed"
    assert stack.sql(f"select count(*) from grading_attempts where submission_id = {int(submission_id)}") == "1"


def test_the_shipped_image_rejects_retired_configuration_before_serving(stacks):
    stack = stacks[1]
    check = ("run", "--rm", "--no-deps", "api", "python", "-m", "web.main", "--check")
    assert "configuration is valid" in stack.compose(*check).stdout
    rejected = stack.compose("run", "--rm", "--no-deps", "-e", "SANDBOX_POOL_SIZE=3", *check[3:], check=False)
    assert rejected.returncode != 0
    assert "SANDBOX_POOL_SIZE" in rejected.stderr and "max_sandboxes" in rejected.stderr
