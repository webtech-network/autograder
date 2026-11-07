"""Fixture retrieval maps one logical reference to its own bytes, with no cache (#390)."""
# pylint: disable=missing-function-docstring
import inspect
import io
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from unittest.mock import Mock

import boto3
import pytest
from botocore.config import Config
from botocore.exceptions import NoCredentialsError
from botocore.response import StreamingBody
from botocore.stub import Stubber

from autograder import build_pipeline
from autograder.models.capabilities import FixtureNotFound, HostCapabilities
from autograder.models.evaluation_error import EvaluationError
from autograder.models.execution import StagedFixture
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


def test_a_missing_bucket_needs_an_operator_and_is_not_retryable():
    _, client = fake_s3_provider({"key": b"x"}, bucket="real")
    wrong = S3FixtureProvider(bucket="other", client_factory=lambda: client)
    with pytest.raises(EvaluationError) as refused:
        wrong("key")
    assert (refused.value.code, refused.value.category, refused.value.retryable) == (
        "FIXTURE_PROVIDER_UNAVAILABLE", "capability", False)


def test_without_a_bucket_the_host_supplies_no_fixture_store():
    # Before COR-03 an unset bucket was a provider that failed every fixture as a retryable PREPARATION_ERROR.
    assert S3FixtureProvider.from_environment({}) is None
    with pytest.raises(ValueError, match="needs a bucket"):
        S3FixtureProvider(bucket=None, client_factory=Mock())
    owned = session()
    outcome = build_pipeline(definition=fixtures_definition(("data.csv", "data.csv", True)),
        capabilities=HostCapabilities(execution=lambda language, budget: owned,
                                      fixtures=S3FixtureProvider.from_environment({}))).run(submission()).outcome
    assert (outcome.error.code, outcome.error.retryable) == ("FIXTURE_PROVIDER_UNAVAILABLE", False)


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
        stub.add_client_error("get_object", "SlowDown", http_status_code=503,
                              expected_params={"Bucket": "fixtures", "Key": "busy"})
        assert provider("a/b") == b"slash"
        assert provider("a_b") == b""
        with pytest.raises(FixtureNotFound):
            provider("missing")
        with pytest.raises(EvaluationError) as denied:
            provider("private")
        assert (denied.value.code, denied.value.retryable) == ("FIXTURE_PROVIDER_UNAVAILABLE", False)
        with pytest.raises(FixtureProviderError):
            provider("busy")
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


def test_pipeline_stages_the_fetched_set_in_one_call_with_placement_chosen_by_the_session():
    provider, client = fake_s3_provider({**COLLIDING, "empty": b""})
    owned = session()
    outcome = build_pipeline(definition=fixtures_definition(
        ("a_b", "under.txt", True), ("a/b", "slash.txt", False), ("empty", "empty.txt", True),
        ("a/b", "copy/slash.txt", True)),
        capabilities=HostCapabilities(execution=lambda language, budget: owned, fixtures=provider)).run(submission()).outcome
    assert outcome.status == "completed"
    owned.stage_fixtures.assert_called_once_with([
        StagedFixture("under.txt", b"underscore content", True), StagedFixture("slash.txt", b"slash content", False),
        StagedFixture("empty.txt", b"", True), StagedFixture("copy/slash.txt", b"slash content", True)])
    assert [key for _, key in client.requests] == ["a_b", "a/b", "empty", "a/b"]
    owned.close.assert_called_once()


def test_a_missing_fixture_after_present_ones_stages_nothing_and_no_fixtures_stage_nothing():
    provider, _ = fake_s3_provider({"present": b"x"})
    owned = session()
    outcome = build_pipeline(definition=fixtures_definition(("present", "p", True), ("absent", "a", True)),
        capabilities=HostCapabilities(execution=lambda language, budget: owned, fixtures=provider)).run(submission()).outcome
    assert outcome.error.code == "PREPARATION_ERROR" and outcome.error.retryable is False
    owned.stage_fixtures.assert_not_called()
    owned = session()
    outcome = build_pipeline(definition=fixtures_definition(),
        capabilities=HostCapabilities(execution=lambda language, budget: owned, fixtures=provider)).run(submission()).outcome
    assert outcome.status == "completed"
    owned.stage_fixtures.assert_not_called()


@pytest.mark.parametrize("unreachable, retryable", [(False, False), (True, True)])
def test_missing_and_failed_fixtures_share_the_safe_preparation_outcome(unreachable, retryable):
    provider, client = fake_s3_provider({"present": b"x"})
    client.unreachable = unreachable
    owned = session()
    outcome = build_pipeline(definition=fixtures_definition(("absent" if not unreachable else "present", "f", True)),
        capabilities=HostCapabilities(execution=lambda language, budget: owned, fixtures=provider)).run(submission()).outcome
    assert outcome.status == "failed" and outcome.score is None and outcome.tree is None
    assert (outcome.error.category, outcome.error.code) == ("capability", "PREPARATION_ERROR")
    assert outcome.error.message == "Assignment preparation could not complete."
    assert outcome.error.retryable is retryable
    owned.stage_fixtures.assert_not_called()
    owned.close.assert_called_once()


class _S3ErrorServer(ThreadingHTTPServer):
    """A local HTTP endpoint answering every GET with one S3 error document, counting requests."""
    def __init__(self, status, code):
        self.status, self.code, self.requests = status, code, 0
        super().__init__(("127.0.0.1", 0), _S3ErrorHandler)


class _S3ErrorHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # pylint: disable=invalid-name  # http.server's handler name
        self.server.requests += 1
        body = (f'<?xml version="1.0" encoding="UTF-8"?><Error><Code>{self.server.code}</Code>'
                f'<Message>refused</Message><RequestId>1</RequestId></Error>').encode()
        self.send_response(self.server.status)
        self.send_header("Content-Type", "application/xml")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # pylint: disable=arguments-differ
        pass


@pytest.mark.parametrize("status, code, retryable", [
    (403, "AccessDenied", False), (404, "NoSuchBucket", False), (403, "InvalidAccessKeyId", False),
    (403, "SignatureDoesNotMatch", False), (503, "SlowDown", True), (500, "InternalError", True)])
def test_store_answers_over_http_are_classified_and_never_retried_by_the_sdk(status, code, retryable):
    """The shipped boto3 client over real HTTP: a refusal needs an operator, a 5xx can pass.

    Either way the provider asks once; the HTTP host's job retry is the only retry layer.
    """
    server = _S3ErrorServer(status, code)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        provider = S3FixtureProvider(bucket="fixtures", endpoint_url=f"http://127.0.0.1:{server.server_address[1]}",
                                     access_key="test", secret_key="test")
        with pytest.raises((EvaluationError, FixtureProviderError)) as failure:
            provider("course/data.csv")
    finally:
        server.shutdown()
        server.server_close()
    if retryable:
        assert type(failure.value) is FixtureProviderError  # pylint: disable=unidiomatic-typecheck
    else:
        assert (failure.value.code, failure.value.retryable) == ("FIXTURE_PROVIDER_UNAVAILABLE", False)
    assert server.requests == 1


def test_missing_credentials_are_not_retryable():
    client = boto3.client("s3", region_name="us-east-1", config=Config(signature_version="s3v4"))
    client.meta.events.register("before-sign.s3.*", raise_no_credentials)
    provider = S3FixtureProvider(bucket="fixtures", client_factory=lambda: client)
    with pytest.raises(EvaluationError) as refused:
        provider("course/data.csv")
    assert (refused.value.code, refused.value.retryable) == ("FIXTURE_PROVIDER_UNAVAILABLE", False)


def raise_no_credentials(**_):
    raise NoCredentialsError()
