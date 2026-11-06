"""The API refuses to start on retired or incoherent configuration (ENV-05, #426).

Each case builds the application exactly as ``web.main`` does at import, from
the process environment, and expects a message naming the offending variable.
Nothing here needs a database, Docker or the network: configuration is checked
before any of them is touched.
"""
# pylint: disable=missing-function-docstring
import os
import subprocess
import sys
from pathlib import Path

import pytest

from execution_host.docker import DockerHost
from web.core.config import RETIRED
from web.main import create_app

ROOT = Path(__file__).resolve().parents[2]
#: Every variable the API reads or rejects, so a developer's shell cannot leak in.
API_VARIABLES = (*RETIRED, "SANDBOX_MODE", "SANDBOX_CONFIG_FILE", "S3_ENDPOINT_URL", "EXTERNAL_ASSETS_BUCKET_NAME",
                 "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "WEB_WORKER_COUNT", "WEB_LEASE_SECONDS", "JSON_LOGS",
                 "LOG_LEVEL")


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in API_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AUTOGRADER_INTEGRATION_TOKEN", "startup-token")


@pytest.mark.parametrize(("variable", "value", "message"), [
    ("SANDBOX_POOL_SIZE", "3", r"SANDBOX_POOL_SIZE: .*general\.max_sandboxes"),
    ("CRITERIA_ASSETS_BUCKET_NAME", "autograder-assets", "CRITERIA_ASSETS_BUCKET_NAME: renamed EXTERNAL_ASSETS_BUCKET_NAME"),
    ("AWS_ACCESS_ID", "key", "AWS_ACCESS_ID: use AWS_ACCESS_KEY_ID"),
    ("UPSTASH_REDIS_URL", "https://example.upstash.io", "UPSTASH_REDIS_URL: the Upstash exporter was removed"),
    ("API_PORT", "8000", "API_PORT: the image serves on 0.0.0.0:8000"),
])
def test_retired_variable_stops_startup_with_its_replacement(monkeypatch, variable, value, message):
    monkeypatch.setenv(variable, value)
    with pytest.raises(ValueError, match=message):
        create_app(start_workers=False)


def test_every_retired_variable_is_reported_at_once(monkeypatch):
    for name in RETIRED:
        monkeypatch.setenv(name, "set")
    with pytest.raises(ValueError) as rejected:
        create_app(start_workers=False)
    assert all(f"{name}: " in str(rejected.value) for name in RETIRED)


def test_retired_variable_left_empty_is_not_an_error(monkeypatch):
    # Compose writes `UPSTASH_REDIS_URL: ${UPSTASH_REDIS_URL:-}` as an empty value.
    monkeypatch.setenv("UPSTASH_REDIS_URL", "")
    monkeypatch.setenv("SANDBOX_POOL_SIZE", "  ")
    assert create_app(start_workers=False).state.host.settings.SANDBOX_MODE == "local"


@pytest.mark.parametrize(("variable", "value", "message"), [
    ("SANDBOX_MODE", "hybrid", "SANDBOX_MODE must be local or remote, got 'hybrid'"),
    ("WEB_WORKER_COUNT", "two", "WEB_WORKER_COUNT must be an integer, got 'two'"),
    ("WEB_LEASE_SECONDS", "soon", "WEB_LEASE_SECONDS must be a number, got 'soon'"),
    ("JSON_LOGS", "maybe", "JSON_LOGS must be true or false, got 'maybe'"),
    ("LOG_LEVEL", "LOUD", "LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR or CRITICAL, got 'LOUD'"),
])
def test_invalid_value_stops_startup_naming_the_variable(monkeypatch, variable, value, message):
    monkeypatch.setenv(variable, value)
    with pytest.raises(ValueError, match=message):
        create_app(start_workers=False)


def test_fixture_store_without_a_bucket_stops_startup(monkeypatch):
    # Before: grading failed later with a retryable PREPARATION_ERROR while /ready said ready.
    monkeypatch.setenv("S3_ENDPOINT_URL", "http://ministack:4566")
    with pytest.raises(ValueError, match="S3_ENDPOINT_URL is set but EXTERNAL_ASSETS_BUCKET_NAME is not"):
        create_app(start_workers=False)


@pytest.mark.parametrize("variable", ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"])
def test_half_a_credential_stops_startup(monkeypatch, variable):
    monkeypatch.setenv("EXTERNAL_ASSETS_BUCKET_NAME", "fixtures")
    monkeypatch.setenv(variable, "only-one-half")
    with pytest.raises(ValueError, match="Set both AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY, or neither"):
        create_app(start_workers=False)


def test_unknown_mode_is_rejected_by_the_execution_host_too():
    # The Action builds its host from the environment without the web settings.
    with pytest.raises(ValueError, match="SANDBOX_MODE must be local or remote, got 'hybrid'"):
        DockerHost(mode="hybrid")


def test_coherent_configuration_starts_without_touching_providers(monkeypatch):
    monkeypatch.setenv("EXTERNAL_ASSETS_BUCKET_NAME", "fixtures")
    monkeypatch.setenv("S3_ENDPOINT_URL", "http://ministack:4566")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "id")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    host = create_app(start_workers=False).state.host
    assert host.capabilities.fixtures.bucket == "fixtures"
    assert host.capabilities.fixtures._client is None  # pylint: disable=protected-access  # still lazy
    assert host.resource_owner._manager is None  # pylint: disable=protected-access  # no Docker yet


def check(**environment):
    """``python -m web.main --check`` as a deployment runs it before replacing the API."""
    env = {key: value for key, value in os.environ.items() if key not in API_VARIABLES}
    env.update(AUTOGRADER_INTEGRATION_TOKEN="startup-token", **environment)
    return subprocess.run([sys.executable, "-m", "web.main", "--check"], cwd=ROOT, env=env,
                          capture_output=True, text=True, timeout=60, check=False)


def test_the_check_command_accepts_valid_configuration():
    result = check()
    assert result.returncode == 0, result.stderr
    assert "configuration is valid" in result.stdout


def test_the_check_command_rejects_retired_configuration():
    result = check(SANDBOX_POOL_SIZE="3")
    assert result.returncode != 0
    assert "SANDBOX_POOL_SIZE" in result.stderr and "max_sandboxes" in result.stderr
