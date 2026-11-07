"""Fixture store failures are classified against a real S3-compatible store (COR-03).

A ministack container (the store the Compose stack uses) answers for a missing
key, a missing bucket and, once stopped, an unreachable endpoint; the shipped
``S3FixtureProvider`` talks to it with the real boto3 client, and the outcome comes
from the real pipeline. Only a condition that can pass without an operator is
retryable: the HTTP host retries it, and retrying a missing bucket would only delay
the student's failure. ministack does not enforce credentials, so access denial is
covered against a real HTTP S3 error answer in ``tests/unit/test_fixture_provider.py``.
"""
# pylint: disable=missing-function-docstring,redefined-outer-name
import time
from uuid import uuid4

import boto3
import docker
import pytest
from botocore.config import Config

from autograder import build_pipeline
from autograder.models.capabilities import FixtureNotFound, HostCapabilities
from autograder.models.evaluation_error import EvaluationError
from execution_host.fixtures import FixtureProviderError, S3FixtureProvider
from tests.unit.pipeline.test_host_capabilities import definition, session, submission

STORE_IMAGE = "ministackorg/ministack:1.3"  # the docker-compose.yml fixture store
BUCKET = "fixtures"


@pytest.fixture(scope="module")
def store():
    try:
        client = docker.from_env()
        client.ping()
    except docker.errors.DockerException as exc:  # pragma: no cover - environment guard
        pytest.skip(f"Docker unavailable: {exc}")
    # With Docker present, a failed pull is a failure: this is acceptance evidence, not optional.
    if not client.images.list(STORE_IMAGE):
        client.images.pull(STORE_IMAGE)
    container = client.containers.run(STORE_IMAGE, name=f"autograder-test-store-{uuid4().hex[:12]}", detach=True,
                                      ports={"4566/tcp": ("127.0.0.1", None)})
    try:
        container.reload()
        endpoint = f"http://127.0.0.1:{container.ports['4566/tcp'][0]['HostPort']}"
        admin = boto3.client("s3", endpoint_url=endpoint, region_name="us-east-1", aws_access_key_id="test",
                             aws_secret_access_key="test", config=Config(signature_version="s3v4"))
        deadline = time.monotonic() + 60
        while True:  # until the store answers
            try:
                admin.create_bucket(Bucket=BUCKET)
                break
            except Exception:  # pylint: disable=broad-exception-caught
                if time.monotonic() > deadline:
                    raise
                time.sleep(0.2)
        admin.put_object(Bucket=BUCKET, Key="course/data.csv", Body=b"a,b\n")
        yield {"endpoint": endpoint, "container": container}
    finally:
        container.remove(force=True)
        client.close()


def provider(store, bucket=BUCKET):
    return S3FixtureProvider(bucket=bucket, endpoint_url=store["endpoint"], access_key="test", secret_key="test")


def grade(fixtures, reference):
    owned = session()
    outcome = build_pipeline(definition=definition(preparation={"fixtures": [
        {"reference": reference, "path": "data.csv", "read_only": True}]}),
        capabilities=HostCapabilities(execution=lambda language, budget: owned, fixtures=fixtures)).run(
            submission()).outcome
    owned.close.assert_called_once()
    return outcome


def test_present_and_missing_keys(store):
    assert provider(store)("course/data.csv") == b"a,b\n"
    with pytest.raises(FixtureNotFound):
        provider(store)("course/absent.csv")
    outcome = grade(provider(store), "course/absent.csv")
    assert (outcome.error.code, outcome.error.retryable) == ("PREPARATION_ERROR", False)
    assert grade(provider(store), "course/data.csv").status == "completed"


def test_a_missing_bucket_is_not_retryable(store):
    missing = provider(store, bucket="no-such-bucket-" + uuid4().hex[:8])
    with pytest.raises(EvaluationError) as refused:
        missing("course/data.csv")
    assert (refused.value.code, refused.value.retryable) == ("FIXTURE_PROVIDER_UNAVAILABLE", False)
    outcome = grade(missing, "course/data.csv")
    assert outcome.status == "failed" and outcome.score is None
    assert (outcome.error.category, outcome.error.code, outcome.error.retryable) == (
        "capability", "FIXTURE_PROVIDER_UNAVAILABLE", False)
    assert outcome.error.message == "The fixture provider is unavailable."


def test_zz_an_unreachable_store_is_retryable(store):
    """Runs last: it stops the store."""
    store["container"].stop(timeout=5)
    with pytest.raises(FixtureProviderError):
        provider(store)("course/data.csv")
    outcome = grade(provider(store), "course/data.csv")
    assert (outcome.error.category, outcome.error.code, outcome.error.retryable) == (
        "capability", "PREPARATION_ERROR", True)
