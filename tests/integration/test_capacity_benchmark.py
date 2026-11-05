"""Opt-in: the capacity benchmark command against real HTTP, PostgreSQL and Docker.

Set TEST_POSTGRES_URL (as for tests/web/test_durable_workers.py) and build the
sandbox images (``make sandbox-build-all``). Each test starts its own uvicorn
process on a private PostgreSQL database with local Docker sandboxes, then runs
``scripts/capacity_benchmark.py`` exactly as an operator would. Assertions cover
termination, failure codes and cleanup only; no timing is asserted.
"""
import asyncio
from contextlib import contextmanager
import json
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
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from autograder.models.language import Language
from sandbox_manager.ownership import LABEL_OWNER_PROCESS, process_start_ticks, read_boot_id
from tests.sandbox_profiles import TEST_IMAGES, sandbox_config

REPO = Path(__file__).resolve().parents[2]
BENCHMARK = REPO / "scripts" / "capacity_benchmark.py"
ALIASES = ("capacity-benchmark-python-io", "capacity-benchmark-webdev")


async def _sql(url, *statements):
    engine = create_async_engine(url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            results = [await connection.execute(text(statement)) for statement in statements]
            return [result.all() if result.returns_rows else None for result in results]
    finally:
        await engine.dispose()


@pytest.fixture
def database_url():
    """A private database on the TEST_POSTGRES_URL server, dropped afterwards."""
    url = os.getenv("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL is required for the HTTP capacity benchmark test")
    docker = pytest.importorskip("docker")
    try:
        client = docker.from_env()
        client.images.get(TEST_IMAGES[Language.PYTHON])
        client.close()
    except Exception as exc:  # pylint: disable=broad-exception-caught
        pytest.skip(f"Docker with the sandbox images is required: {exc}")
    name = "capacity_benchmark_" + uuid4().hex[:12]
    asyncio.run(_sql(url, f'CREATE DATABASE "{name}"'))
    try:
        yield make_url(url).set(database=name).render_as_string(hide_password=False)
    finally:
        asyncio.run(_sql(url, f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))


@contextmanager
def api_stack(directory, database_url, languages):
    """uvicorn with durable workers and local sandboxes: the stack the benchmark measures."""
    config = directory / "sandbox.yml"
    config.write_text(sandbox_config(languages=languages, pool_size=0, max_sandboxes=8))
    receipts = directory / "receipts"
    token = secrets.token_hex(24)
    env = dict(os.environ, DATABASE_URL=database_url, AUTOGRADER_INTEGRATION_TOKEN=token,
               SANDBOX_MODE="local", SANDBOX_CONFIG_FILE=str(config), WEB_WORKER_COUNT="2",
               WEB_POLL_SECONDS="0.2", WEB_OUTCOME_RECEIPT_DIR=str(receipts), LOG_LEVEL="WARNING",
               APP_ENV="test", PYTHON_DOTENV_DISABLED="1")
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(256)
    url = f"http://127.0.0.1:{listener.getsockname()[1]}"
    # The API never creates tables; migrate first, exactly as a deployment does.
    migration = subprocess.run([sys.executable, "-m", "alembic", "-c", "web/alembic.ini", "upgrade", "head"],
                               cwd=REPO, env=env, capture_output=True, text=True, timeout=120, check=False)
    if migration.returncode:
        pytest.fail("Migrating the benchmark database failed:\n" + migration.stderr)
    log_path = directory / "server.log"
    with log_path.open("w") as log:
        process = subprocess.Popen([sys.executable, "-m", "uvicorn", "web.main:app", "--fd", str(listener.fileno()),
                                    "--log-level", "warning"], cwd=REPO, env=env, pass_fds=(listener.fileno(),),
                                   stdout=log, stderr=subprocess.STDOUT)
        listener.close()
        try:
            deadline = time.monotonic() + 60
            while True:
                if process.poll() is not None:
                    pytest.fail("API exited during startup:\n" + log_path.read_text())
                try:
                    if requests.get(url + "/api/v1/ready", timeout=1).status_code == 200:
                        break
                except requests.RequestException:
                    pass
                if time.monotonic() > deadline:
                    pytest.fail("API startup timed out:\n" + log_path.read_text())
                time.sleep(0.05)
            # Local mode: the API process owns its sandboxes; select exactly those.
            owner = f"{read_boot_id() or 'unknown'}:{process.pid}:{process_start_ticks(process.pid) or 'unknown'}"
            yield {"url": url, "token": token, "pid": process.pid, "receipts": receipts, "log": log_path,
                   "sandbox_label": f"{LABEL_OWNER_PROCESS}={owner}"}
        finally:
            process.terminate()
            try:
                process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)


def run_benchmark(stack, *args):
    completed = subprocess.run(
        [sys.executable, str(BENCHMARK), "--url", stack["url"], "--api-pid", str(stack["pid"]),
         "--sandbox-label", stack["sandbox_label"], "--poll-interval", "0.2", "--timeout", "600", *args],
        cwd=REPO, env=dict(os.environ, AUTOGRADER_INTEGRATION_TOKEN=stack["token"]),
        capture_output=True, text=True, timeout=900, check=False)
    assert completed.stdout, completed.stderr + "\n" + stack["log"].read_text()
    return completed.returncode, json.loads(completed.stdout), completed.stderr


# This test verifies the benchmark, not the stack's capacity: sandbox failures the stack
# reports under host load (PRF-01 capacity, Docker errors) are terminal outcomes, tolerated here.
MIX = ("--workload", "mix", "--submissions", "20", "--executions", "2", "--criteria", "10", "--page-kb", "5",
       "--allow-failure", "CAPABILITY_UNAVAILABLE", "--allow-failure", "SANDBOX_ERROR")


def test_bursts_terminate_and_leave_nothing_behind(tmp_path, database_url):
    with api_stack(tmp_path, database_url, (Language.PYTHON, Language.NODE)) as stack:
        first_code, first, first_summary = run_benchmark(stack, *MIX)
        second_code, second, _ = run_benchmark(stack, *MIX, "--runs", "2")
        headers = {"Authorization": "Bearer " + stack["token"]}
        configs = {alias: requests.get(f"{stack['url']}/api/v1/configs/{alias}", headers=headers, timeout=10).json()
                   for alias in ALIASES}
        active = requests.get(f"{stack['url']}/api/v1/configs", headers=headers, timeout=10).json()
        receipts = sorted(stack["receipts"].glob("*")) if stack["receipts"].exists() else []

    assert first_code == 0, first_summary
    assert second_code == 0, second["problems"]
    assert first["passed"] and second["passed"]
    assert "PASS" in first_summary
    runs = first["runs"] + second["runs"]
    assert len(runs) == 3 and second["variance"] is not None
    for run in runs:
        context = json.dumps(run)  # Shown on failure: the run's full report.
        assert run["acceptance"] == run["acceptance"] | {"requested": 20, "accepted": 20, "status_codes": {"202": 20}}, context
        assert run["drain"]["terminal"] == 20 and run["drain"]["non_terminal"] == 0, context
        assert run["outcomes"]["completed"] + run["outcomes"]["failed"] == 20, context
        assert set(run["outcomes"]["scores"]) == {"100.0"}, context
        assert run["executions"]["requested"] == 2, context
        assert run["queue_wait_seconds"]["count"] == 20 and run["grading_duration_seconds"]["count"] == 20, context
        assert run["sandboxes"]["peak"] >= 1 and run["sandboxes"]["leftover"] == 0, context
        assert run["api_rss_mb"]["peak"] > 0, context
    assert first["environment"]["client"]["logical_cpus"] == os.cpu_count()

    # Re-running reuses two configurations and leaves them inactive; no receipt survives publication.
    assert all(config["is_active"] is False for config in configs.values())
    assert not [config for config in active if config["external_assignment_id"] in ALIASES]
    assert receipts == []
    configs_count, operation_receipts, statuses = asyncio.run(_sql(
        database_url, "SELECT count(*) FROM grading_configurations", "SELECT count(*) FROM operation_receipts",
        "SELECT status, count(*) FROM submissions GROUP BY status"))
    assert configs_count == [(2,)] and operation_receipts == [(0,)]
    terminal = {str(status).lower().rsplit(".", 1)[-1]: count for status, count in statuses}
    assert set(terminal) <= {"completed", "failed"} and sum(terminal.values()) == 60


def test_unexpected_failure_codes_fail_the_benchmark(tmp_path, database_url):
    # A host without a Python runtime: every Python grading fails as an unavailable capability.
    with api_stack(tmp_path, database_url, (Language.NODE,)) as stack:
        failing_code, failing, failing_summary = run_benchmark(stack, "--submissions", "5", "--tests", "1")
        allowed_code, allowed, _ = run_benchmark(stack, "--submissions", "5", "--tests", "1",
                                                 "--allow-failure", "CAPABILITY_UNAVAILABLE")

    assert failing_code == 1 and not failing["passed"]
    assert failing["runs"][0]["outcomes"]["failure_codes"] == {"CAPABILITY_UNAVAILABLE": 5}
    assert failing["runs"][0]["drain"]["non_terminal"] == 0
    assert "unexpected failure codes" in failing_summary
    assert allowed_code == 0 and allowed["passed"]
