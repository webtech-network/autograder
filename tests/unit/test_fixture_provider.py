"""Fixture retrieval maps one logical reference to its own bytes, with no cache (#390)."""
# pylint: disable=missing-function-docstring
import inspect
import io
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock

import boto3
import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber

from autograder import build_pipeline
from autograder.models.capabilities import FixtureNotFound, HostCapabilities
from execution_host.docker import DockerHost, docker_capabilities
from execution_host.fixtures import FixtureProviderError, S3FixtureProvider
from tests.fake_object_store import fake_s3_provider
from tests.unit.pipeline.test_host_capabilities import definition, session, submission


COLLIDING = {"a/b": b"slash content", "a_b": b"underscore content"}


@pytest.mark.parametrize("order", [("a/b", "a_b"), ("a_b", "a/b")])
def test_slash_and_underscore_references_never_share_content(order):
    provider, client = fake_s3_provider(COLLIDING)
    assert [provider(reference) for reference in order] == [COLLIDING[reference] for reference in order]
    assert client.requests == [("fixtures", reference) for reference in order]


def test_every_request_reads_the_store_so_replacement_is_visible():
    provider, client = fake_s3_provider({"data.csv": b"v1"})
    assert provider("data.csv") == b"v1"
    client.objects["data.csv"] = b"v2"
    assert provider("data.csv") == b"v2"
    assert len(client.requests) == 2


def test_empty_object_is_valid_content_every_time():
    provider, _ = fake_s3_provider({"empty": b""})
    assert provider("empty") == b""
    assert provider("empty") == b""


def test_missing_reference_is_distinct_from_provider_failure():
    provider, client = fake_s3_provider({"present": b"x"})
    with pytest.raises(FixtureNotFound):
        provider("absent")
    client.unreachable = True
    with pytest.raises(FixtureProviderError) as failure:
        provider("present")
    assert not isinstance(failure.value, FixtureNotFound)


def test_wrong_bucket_and_missing_configuration_are_provider_failures():
    _, client = fake_s3_provider({"key": b"x"}, bucket="real")
    wrong = S3FixtureProvider(bucket="other", client_factory=lambda: client)
    with pytest.raises(FixtureProviderError):
        wrong("key")
    factory = Mock()
    with pytest.raises(FixtureProviderError):
        S3FixtureProvider(bucket=None, client_factory=factory)("key")
    factory.assert_not_called()


def test_retrieval_accepts_only_a_logical_reference():
    assert list(inspect.signature(S3FixtureProvider.__call__).parameters) == ["self", "reference"]


def test_real_boto3_client_responses_and_errors_are_mapped():
    client = boto3.client("s3", region_name="us-east-1", aws_access_key_id="test",
                          aws_secret_access_key="test")
    provider = S3FixtureProvider(bucket="fixtures", client_factory=lambda: client)
    with Stubber(client) as stub:
        for key, content in (("a/b", b"slash"), ("a_b", b""), ):
            stub.add_response("get_object", {"Body": StreamingBody(io.BytesIO(content), len(content))},
                              {"Bucket": "fixtures", "Key": key})
        stub.add_client_error("get_object", "NoSuchKey", http_status_code=404,
                              expected_params={"Bucket": "fixtures", "Key": "missing"})
        stub.add_client_error("get_object", "AccessDenied", http_status_code=403,
                              expected_params={"Bucket": "fixtures", "Key": "private"})
        assert provider("a/b") == b"slash"
        assert provider("a_b") == b""
        with pytest.raises(FixtureNotFound):
            provider("missing")
        with pytest.raises(FixtureProviderError):
            provider("private")
        stub.assert_no_pending_responses()


def test_client_is_created_lazily_once_and_shared_by_concurrent_requests():
    objects = {f"set/{index}" if index % 2 else f"set_{index}": str(index).encode() for index in range(40)}
    _, client = fake_s3_provider(objects)
    factory = Mock(return_value=client)
    provider = S3FixtureProvider(bucket="fixtures", client_factory=factory)
    factory.assert_not_called()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = dict(zip(objects, pool.map(provider, objects)))
    assert results == objects
    factory.assert_called_once_with()


def test_host_composition_reads_provider_configuration_from_environment(monkeypatch):
    monkeypatch.setenv("EXTERNAL_ASSETS_BUCKET_NAME", "course-fixtures")
    monkeypatch.setenv("S3_ENDPOINT_URL", "http://ministack:4566")
    for capabilities in (DockerHost(mode="local").capabilities, docker_capabilities(Mock())):
        assert isinstance(capabilities.fixtures, S3FixtureProvider)
        assert capabilities.fixtures.bucket == "course-fixtures"
        assert capabilities.fixtures.endpoint_url == "http://ministack:4566"


def fixtures_definition(*fixtures):
    return definition(preparation={"fixtures": [
        {"reference": reference, "path": path, "read_only": read_only} for reference, path, read_only in fixtures]})


def test_pipeline_stages_each_reference_with_placement_chosen_by_the_session():
    provider, client = fake_s3_provider({**COLLIDING, "empty": b""})
    owned = session()
    outcome = build_pipeline(definition=fixtures_definition(
        ("a_b", "under.txt", True), ("a/b", "slash.txt", False), ("empty", "empty.txt", True),
        ("a/b", "copy/slash.txt", True)),
        capabilities=HostCapabilities(execution=lambda language: owned, fixtures=provider)).run(submission()).outcome
    assert outcome.status == "completed"
    assert [call.args for call in owned.stage_fixture.call_args_list] == [
        ("under.txt", b"underscore content", True), ("slash.txt", b"slash content", False),
        ("empty.txt", b"", True), ("copy/slash.txt", b"slash content", True)]
    assert [key for _, key in client.requests] == ["a_b", "a/b", "empty", "a/b"]
    owned.close.assert_called_once()


@pytest.mark.parametrize("unreachable, retryable", [(False, False), (True, True)])
def test_missing_and_failed_fixtures_share_the_safe_preparation_outcome(unreachable, retryable):
    provider, client = fake_s3_provider({"present": b"x"})
    client.unreachable = unreachable
    owned = session()
    outcome = build_pipeline(definition=fixtures_definition(("absent" if not unreachable else "present", "f", True)),
        capabilities=HostCapabilities(execution=lambda language: owned, fixtures=provider)).run(submission()).outcome
    assert outcome.status == "failed" and outcome.score is None and outcome.tree is None
    assert (outcome.error.category, outcome.error.code) == ("capability", "PREPARATION_ERROR")
    assert outcome.error.message == "Assignment preparation could not complete."
    assert outcome.error.retryable is retryable
    owned.stage_fixture.assert_not_called()
    owned.close.assert_called_once()
