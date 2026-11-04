"""More grading workers than sandboxes: a real API process, PostgreSQL and Docker.

The API runs local-mode sandboxes with ``max_sandboxes: 2`` and six grading
workers, so most gradings must wait for a slot. Every accepted submission must
complete (none fails for capacity), deliberate runs mixed in must either run or
answer the defined busy status, and after shutdown no container of the API's
owner lease may remain.

Requires ``TEST_POSTGRES_URL`` (a disposable PostgreSQL; each run creates and
drops its own database) and the ``sandbox-py`` image.
"""
import asyncio
import os
import secrets
import signal
import socket
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import docker
import pytest
import requests
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from sandbox_manager.ownership import APP_FILTER, LABEL_OWNER_PROCESS
from tests.e2e.contracts import create_config, definition, poll, submit
from tests.sandbox_profiles import TEST_IMAGES, sandbox_config
from autograder.models.language import Language

MAX_SANDBOXES = 2
WORKERS = 6
SUBMISSIONS = 12
DELIBERATE_RUNS = 6
# Generous: twelve gradings through two sandboxes on a loaded shared machine.
FINISH_SECONDS = 300

# Three I/O criteria share one sandbox per grading and take long enough that
# the six workers really contend for the two slots.
PROGRAM = "import time\nname = input()\ntime.sleep(0.5)\nprint(f'Hello, {name}')\n"
DEFINITION = definition(template="input_output", tests=[
    {"id": f"greets-{name.lower()}", "name": f"Greets {name}", "type": "expect_output",
     "parameters": {"program_command": "python3 main.py", "inputs": [name], "expected_output": f"Hello, {name}"}}
    for name in ("Ada", "Grace", "Linus")])


async def _admin(url, statement):
    engine = create_async_engine(url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.execute(text(statement))
    finally:
        await engine.dispose()


async def _statuses(url):
    engine = create_async_engine(url)
    try:
        async with engine.connect() as connection:
            rows = await connection.execute(text(
                "SELECT lower(s.status::text), r.outcome -> 'error' ->> 'code', r.final_score "
                "FROM submissions s LEFT JOIN submission_results r ON r.submission_id = s.id"))
            return [tuple(row) for row in rows]
    finally:
        await engine.dispose()


@pytest.fixture(scope="module")
def database_url():
    base = os.getenv("TEST_POSTGRES_URL")
    if not base:
        pytest.skip("TEST_POSTGRES_URL is required for the HTTP sandbox budget test")
    name = "budget_e2e_" + uuid4().hex[:12]
    asyncio.run(_admin(base, f'CREATE DATABASE "{name}"'))
    url = make_url(base).set(database=name).render_as_string(hide_password=False)
    yield url
    asyncio.run(_admin(base, f'DROP DATABASE "{name}" WITH (FORCE)'))


@pytest.fixture(scope="module")
def docker_client():
    try:
        client = docker.from_env()
        client.images.get(TEST_IMAGES[Language.PYTHON])
    except Exception as exc:  # pragma: no cover - environment guard
        pytest.skip(f"Docker or {TEST_IMAGES[Language.PYTHON]} unavailable: {exc}")
    yield client
    client.close()


@pytest.fixture(scope="module")
def budget_api(tmp_path_factory, database_url, docker_client):  # pylint: disable=unused-argument
    directory = tmp_path_factory.mktemp("budget-e2e")
    config = directory / "sandbox.yml"
    config.write_text(sandbox_config((Language.PYTHON,), max_sandboxes=MAX_SANDBOXES))
    token = secrets.token_hex(24)
    env = dict(os.environ, DATABASE_URL=database_url, AUTOGRADER_INTEGRATION_TOKEN=token,
               SANDBOX_MODE="local", SANDBOX_CONFIG_FILE=str(config), WEB_WORKER_COUNT=str(WORKERS),
               WEB_POLL_SECONDS="0.1", WEB_OUTCOME_RECEIPT_DIR=str(directory / "receipts"),
               LOG_LEVEL="WARNING", APP_ENV="test", PYTHON_DOTENV_DISABLED="1")
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(128)
    url = f"http://127.0.0.1:{listener.getsockname()[1]}/api/v1"
    log_path = directory / "server.log"
    with log_path.open("w") as log:
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "web.main:app", "--fd", str(listener.fileno()),
                                    "--log-level", "warning"], cwd=Path(__file__).resolve().parents[2], env=env,
                                   pass_fds=(listener.fileno(),), stdout=log, stderr=subprocess.STDOUT)
        listener.close()
        state = {"url": url, "headers": {"Authorization": "Bearer " + token}, "process": process,
                 "log": log_path, "database_url": database_url}
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    pytest.fail("API exited during startup:\n" + log_path.read_text())
                try:
                    if requests.get(url + "/ready", timeout=0.5).status_code == 200:
                        break
                except requests.RequestException:
                    pass
                time.sleep(0.05)
            else:
                pytest.fail("API startup timed out:\n" + log_path.read_text())
            yield state
        finally:
            stop(process)


def stop(process):
    if process.poll() is None:
        process.terminate()  # Graceful: the lifespan drains workers and shuts the sandbox manager down.
        try:
            process.wait(timeout=120)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def owned_containers(client, pid):
    """Containers whose owner lease names this process id (boot:pid:start ticks)."""
    return [container for container in client.containers.list(all=True, filters=APP_FILTER)
            if container.labels.get(LABEL_OWNER_PROCESS, "").split(":")[1:2] == [str(pid)]]


def submit_burst(api):
    config = create_config(api["url"], api["headers"], DEFINITION)
    files = [{"filename": "main.py", "content": PROGRAM}]
    return [submit(api["url"], api["headers"], config, files)["id"] for _ in range(SUBMISSIONS)]


def assert_all_completed(api, ids):
    with ThreadPoolExecutor(len(ids)) as executor:
        results = list(executor.map(lambda i: poll(api["url"], api["headers"], i, timeout=FINISH_SECONDS), ids))
    failures = [(result["outcome"].get("error") or {}).get("code") for result in results
                if result["outcome"]["status"] != "completed"]
    assert failures == [], f"{len(failures)}/{len(ids)} gradings failed: {failures}"
    assert all(result["outcome"]["score"] == 100 for result in results)


def test_oversubscribed_workers_complete_every_submission(budget_api):
    ids = submit_burst(budget_api)
    assert_all_completed(budget_api, ids)


def test_deliberate_runs_mixed_into_a_grading_burst_never_fail_a_grading(budget_api):
    ids = submit_burst(budget_api)
    request = {"language": "python", "program_command": "python3 main.py", "test_cases": [["Ada"]],
               "submission_files": [{"filename": "main.py", "content": PROGRAM}]}

    def execute(_):
        return requests.post(budget_api["url"] + "/execute", json=request, headers=budget_api["headers"], timeout=120)

    with ThreadPoolExecutor(DELIBERATE_RUNS) as executor:
        responses = list(executor.map(execute, range(DELIBERATE_RUNS)))
    assert_all_completed(budget_api, ids)
    for response in responses:
        if response.status_code == 200:
            assert response.json()["results"][0]["stdout"] == "Hello, Ada\n"
        else:  # Saturated: the defined status, never a generic failure.
            assert response.status_code == 503, response.text
            assert response.json()["detail"]["code"] == "EXECUTION_BUSY"
            assert response.headers["Retry-After"] == "5"


def test_zz_database_holds_only_completed_outcomes_and_shutdown_leaves_no_container(budget_api, docker_client):
    """Runs last in this module: it stops the API."""
    rows = asyncio.run(_statuses(budget_api["database_url"]))
    assert len(rows) == 2 * SUBMISSIONS
    assert set(rows) == {("completed", None, 100.0)}, rows
    process = budget_api["process"]
    stop(process)
    # uvicorn re-raises the handled SIGTERM after its graceful shutdown completes.
    assert process.returncode in (0, -signal.SIGTERM), budget_api["log"].read_text()
    assert owned_containers(docker_client, process.pid) == []
