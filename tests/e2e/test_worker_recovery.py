"""Accepted work survives a sandbox service outage and a killed API process (COR-03).

Real processes only: the private sandbox service (``sandbox_manager.api``) with
local Docker sandboxes, and API processes in remote sandbox mode on their own
PostgreSQL database. Every wait synchronizes on database or process state.

* The sandbox service is stopped, submissions are accepted, and each one's first
  attempt fails with a retryable ``CAPABILITY_UNAVAILABLE`` that is released, not
  published. The service is restarted and every submission completes. Before
  COR-03 each was published ``failed`` on its first attempt.
* An API process is killed with SIGKILL mid-grading; another API process reclaims
  the expired lease and completes the submission (the recovery probe of #418).

Requires ``TEST_POSTGRES_URL`` (each run creates and drops its own database) and
the shipped Python sandbox image.
"""
import asyncio
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

import pytest
import requests
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from autograder.models.language import Language
from tests.e2e.contracts import create_config, definition, poll, submit
# pylint: disable-next=unused-import  # the docker_client and database_url fixtures
from tests.e2e.test_sandbox_budget import database_url, docker_client, owned_containers, stop
from tests.sandbox_profiles import sandbox_config

REPO = Path(__file__).resolve().parents[2]
LEASE_SECONDS = 10
# A released attempt is retried after 2, 4, 8 and 16 s: about 30 s for the service to return.
RETRY_SECONDS = 2
MAX_ATTEMPTS = 5
SUBMISSIONS = 4
FINISH_SECONDS = 180


def program(sleep_seconds=0.0):
    return f"import time\nname = input()\ntime.sleep({sleep_seconds})\nprint(f'Hello, {{name}}')\n"


DEFINITION = definition(template="input_output", tests=[
    {"id": "greets", "name": "Greets", "type": "expect_output",
     "parameters": {"program_command": "python3 main.py", "inputs": ["Ada"], "expected_output": "Hello, Ada"}}])


def listen(port=0):
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", port))
    listener.listen(128)
    return listener


def serve(app, env, listener, log_path):
    """Start uvicorn on an already bound socket (no free-port race); the caller's copy is closed."""
    with log_path.open("a") as log:
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", app, "--fd", str(listener.fileno()),
                                    "--log-level", "warning"], cwd=REPO, env=env,
                                   pass_fds=(listener.fileno(),), stdout=log, stderr=subprocess.STDOUT)
    listener.close()
    return process


def wait_until(condition, timeout, describe, process=None, log_path=None):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            pytest.fail(f"{describe}: process exited\n" + (log_path.read_text() if log_path else ""))
        if condition():
            return
        time.sleep(0.1)
    pytest.fail(f"Timed out waiting until {describe}\n" + (log_path.read_text() if log_path else ""))


def responds(url):
    def check():
        try:
            return requests.get(url, timeout=0.5).status_code == 200
        except requests.RequestException:
            return False
    return check


def query(url, statement, **parameters):
    async def run():
        engine = create_async_engine(url)
        try:
            async with engine.connect() as connection:
                return [tuple(row) for row in await connection.execute(text(statement), parameters)]
        finally:
            await engine.dispose()
    return asyncio.run(run())


def attempts(url, submission_id):
    return query(url, "SELECT number, status FROM grading_attempts WHERE submission_id = :id ORDER BY number",
                 id=submission_id)


@pytest.fixture(scope="module")
def stack(tmp_path_factory, database_url, docker_client):  # pylint: disable=redefined-outer-name,unused-argument
    directory = tmp_path_factory.mktemp("recovery-e2e")
    config = directory / "sandbox.yml"
    config.write_text(sandbox_config((Language.PYTHON,), max_sandboxes=2))
    sandbox_token, token = secrets.token_hex(24), secrets.token_hex(24)
    base = dict(os.environ, LOG_LEVEL="WARNING", PYTHON_DOTENV_DISABLED="1", SANDBOX_CONFIG_FILE=str(config))
    sandbox_env = dict(base, SANDBOX_API_TOKEN=sandbox_token)
    sandbox_port = listen().getsockname()[1]  # closed at once; rebound on every (re)start
    api_env = dict(base, DATABASE_URL=database_url, AUTOGRADER_INTEGRATION_TOKEN=token, APP_ENV="test",
                   SANDBOX_MODE="remote", SANDBOX_API_URL=f"http://127.0.0.1:{sandbox_port}",
                   SANDBOX_API_TOKEN=sandbox_token, WEB_WORKER_COUNT="2", WEB_POLL_SECONDS="0.1",
                   WEB_LEASE_SECONDS=str(LEASE_SECONDS), WEB_RETRY_SECONDS=str(RETRY_SECONDS),
                   WEB_MAX_ATTEMPTS=str(MAX_ATTEMPTS), WEB_OUTCOME_RECEIPT_DIR=str(directory / "receipts"))
    migration = subprocess.run([sys.executable, "-m", "alembic", "-c", "web/alembic.ini", "upgrade", "head"],
                               cwd=REPO, env=api_env, capture_output=True, text=True, timeout=120, check=False)
    if migration.returncode:
        pytest.fail("Migrating the recovery database failed:\n" + migration.stderr)
    state = {"directory": directory, "database_url": database_url, "headers": {"Authorization": "Bearer " + token},
             "api_env": api_env, "sandbox_env": sandbox_env, "sandbox_port": sandbox_port,
             "sandbox_log": directory / "sandbox.log", "api_log": directory / "api.log", "apis": [], "sandbox": None}

    def start_sandbox():
        process = serve("sandbox_manager.api:app", sandbox_env, listen(sandbox_port), state["sandbox_log"])
        wait_until(responds(f"http://127.0.0.1:{sandbox_port}/health"), 60, "the sandbox service is up",
                   process, state["sandbox_log"])
        state["sandbox"] = process
        return process

    def start_api():
        listener = listen()
        url = f"http://127.0.0.1:{listener.getsockname()[1]}/api/v1"
        process = serve("web.main:app", api_env, listener, state["api_log"])
        wait_until(responds(url + "/ready"), 60, "the API is ready", process, state["api_log"])
        state["apis"].append(process)
        state["url"] = url
        return process

    state["start_sandbox"], state["start_api"] = start_sandbox, start_api
    try:
        start_sandbox()
        start_api()
        yield state
    finally:
        for process in state["apis"]:
            stop(process)
        if state["sandbox"] is not None:
            stop(state["sandbox"])


def submit_all(stack, count, source):  # pylint: disable=redefined-outer-name
    config = create_config(stack["url"], stack["headers"], DEFINITION)
    return [submit(stack["url"], stack["headers"], config, [{"filename": "main.py", "content": source}])["id"]
            for _ in range(count)]


def assert_completed(stack, ids):  # pylint: disable=redefined-outer-name
    for submission_id in ids:
        result = poll(stack["url"], stack["headers"], submission_id, timeout=FINISH_SECONDS)
        assert result["outcome"]["status"] == "completed", (result["outcome"], stack["api_log"].read_text())
        assert result["outcome"]["score"] == 100


def test_work_accepted_while_the_sandbox_service_is_down_completes_after_it_returns(stack):
    # pylint: disable=redefined-outer-name
    stop(stack["sandbox"])
    stack["sandbox"] = None
    ids = submit_all(stack, SUBMISSIONS, program())
    url = stack["database_url"]

    def every_first_attempt_released():
        released = query(url, "SELECT DISTINCT submission_id FROM grading_attempts WHERE status = 'released'")
        return {row[0] for row in released} >= set(ids)

    wait_until(every_first_attempt_released, 60, "every submission's first attempt was released",
               stack["apis"][-1], stack["api_log"])
    # Released, not published: no terminal row, polling still says processing.
    assert query(url, "SELECT count(*) FROM submission_results WHERE submission_id = ANY(:ids)", ids=ids) == [(0,)]
    for submission_id in ids:
        polled = requests.get(f"{stack['url']}/submissions/{submission_id}", headers=stack["headers"], timeout=5)
        assert polled.json()["status"] == "processing"
    stack["start_sandbox"]()
    assert_completed(stack, ids)
    for submission_id in ids:
        history = attempts(url, submission_id)
        assert history[-1][1] == "published" and {status for _, status in history[:-1]} == {"released"}, history


def test_a_killed_api_process_is_recovered_by_another(stack, docker_client):
    # pylint: disable=redefined-outer-name
    [submission_id] = submit_all(stack, 1, program(sleep_seconds=5))
    url = stack["database_url"]
    killed = stack["apis"][-1]
    wait_until(lambda: attempts(url, submission_id) == [(1, "running")], 60, "the grading is running",
               killed, stack["api_log"])
    killed.send_signal(signal.SIGKILL)
    killed.wait(timeout=10)
    started = time.monotonic()
    stack["start_api"]()
    assert_completed(stack, [submission_id])
    recovered = time.monotonic() - started
    assert attempts(url, submission_id) == [(1, "expired"), (2, "published")]
    print(f"Recovered a SIGKILLed attempt in {recovered:.1f}s with a {LEASE_SECONDS}s lease")
    # The killed attempt's sandbox belongs to the sandbox service; it ends with the service.
    sandbox = stack["sandbox"]
    stop(sandbox)
    stack["sandbox"] = None
    assert sandbox.returncode in (0, -signal.SIGTERM), stack["sandbox_log"].read_text()
    assert owned_containers(docker_client, sandbox.pid) == []
