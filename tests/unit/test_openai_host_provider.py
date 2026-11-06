"""The shipped OpenAI provider is resolved once per host and bounded (PRF-06).

Lifetime tests inject a counting secret source and client factory. Wire tests
run the real SDK client against a local HTTP stub (never live OpenAI) and
synchronize on the stub's request log; nothing waits on a sleep.
"""
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock

import pytest

from autograder import HostCapabilities, Submission, SubmissionFile, build_pipeline
from autograder.models.process import ProcessResult, ProcessStatus
from execution_host import openai_provider
from execution_host.docker import ConfiguredAssessmentProvider, DockerHost

AI_DEFINITION = {
    "schema_version": "1.0", "templates": ["static_analysis"], "languages": ["python"],
    "criteria": {"base": {"weight": 100, "tests": [
        {"id": "sort", "type": "ai_sorting_algorithm", "name": "Sort", "parameters": {"algorithm_name": "Merge Sort"}},
        {"id": "sort-again", "type": "ai_sorting_algorithm", "name": "Sort",
         "parameters": {"algorithm_name": "Quick Sort"}}]}},
}
STATIC_DEFINITION = {
    "schema_version": "1.0", "templates": ["webdev"], "languages": ["python"],
    "criteria": {"base": {"weight": 100, "tests": [
        {"id": "tag", "type": "has_tag", "name": "Tag", "file": "index.html", "parameters": {"tag": "main"}}]}},
}
IO_DEFINITION = {
    "schema_version": "1.0", "templates": ["input_output"], "languages": ["python"],
    "criteria": {"base": {"weight": 100, "tests": [
        {"id": "sum", "type": "expect_output", "name": "Sum", "parameters": {
            "inputs": ["2", "3"], "expected_output": "5", "program_command": "python3 main.py"}}]}},
}


def ai_submission():
    return Submission("student", "student", "sorting", {"main.py": SubmissionFile("main.py", "def s(a): return a")})


def grade_ai(provider):
    return build_pipeline(definition=AI_DEFINITION, capabilities=HostCapabilities(ai=provider)).run(
        ai_submission()).outcome


def structured(*scores):
    """The Responses API body for a valid structured answer."""
    text = json.dumps({"results": [{"criterion_id": criterion, "feedback": f"feedback {criterion}", "score": score}
                                   for criterion, score in scores]})
    return {"id": "resp_1", "object": "response", "created_at": 0, "model": "test-model", "status": "completed",
            "parallel_tool_calls": False, "tool_choice": "auto", "tools": [],
            "output": [{"type": "message", "id": "msg_1", "role": "assistant", "status": "completed",
                        "content": [{"type": "output_text", "text": text, "annotations": []}]}]}


class FakeClient:
    """Stands in for the SDK client in lifetime tests; answers every criterion."""

    def __init__(self, api_key):
        self.api_key = api_key
        self.responses = self

    def parse(self, *, model, input, text_format):  # pylint: disable=redefined-builtin
        ids = re.findall(r'"criterion_id": "([^"]+)"', input[1]["content"])
        return Mock(output_parsed=text_format(results=[
            openai_provider.TestOutput(criterion_id=criterion, feedback="f", score=50.0) for criterion in ids]))


def counting_provider(**overrides):
    secrets = Mock(return_value="secret-key")
    factory = Mock(side_effect=FakeClient)
    provider = ConfiguredAssessmentProvider(secret_name="AUTOGRADER_OPENAI_KEY", secret_source=secrets,
                                            client_factory=factory, **overrides)
    return provider, secrets, factory


# --- Lifetime: one lookup and one client per host ---------------------------------

def test_many_gradings_share_one_secret_lookup_and_one_client():
    provider, secrets, factory = counting_provider()
    secrets.assert_not_called()
    factory.assert_not_called()
    outcomes = [grade_ai(provider) for _ in range(5)]
    assert [outcome.score for outcome in outcomes] == [50.0] * 5
    secrets.assert_called_once_with("AUTOGRADER_OPENAI_KEY", "OPENAI_API_KEY", "us-east-1")
    factory.assert_called_once_with("secret-key")


def test_concurrent_first_gradings_share_one_secret_lookup_and_one_client():
    provider, secrets, factory = counting_provider()
    entered, release = threading.Event(), threading.Event()

    def slow_lookup(*args):
        entered.set()
        assert release.wait(10)
        return "secret-key"
    secrets.side_effect = slow_lookup
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(grade_ai, provider) for _ in range(16)]
        assert entered.wait(10)  # one thread is resolving while the others queue behind it
        release.set()
        outcomes = [future.result() for future in futures]
    assert {outcome.status for outcome in outcomes} == {"completed"}
    secrets.assert_called_once()
    factory.assert_called_once_with("secret-key")


def test_credential_failure_is_unavailable_and_does_not_poison_the_next_grading():
    provider, secrets, factory = counting_provider()
    secrets.side_effect = [RuntimeError("secrets manager is down: detail"), "secret-key"]
    failed = grade_ai(provider)
    assert failed.status == "failed" and failed.score is None and failed.tree is None
    assert (failed.error.code, failed.error.category) == ("PROVIDER_UNAVAILABLE", "provider")
    assert "detail" not in failed.error.message
    factory.assert_not_called()
    recovered = grade_ai(provider)
    assert recovered.status == "completed" and recovered.score == 50.0
    assert secrets.call_count == 2
    factory.assert_called_once_with("secret-key")


def test_missing_credential_is_unavailable_without_constructing_a_client():
    factory = Mock(side_effect=FakeClient)
    outcome = grade_ai(ConfiguredAssessmentProvider(client_factory=factory))
    assert outcome.error.code == "PROVIDER_UNAVAILABLE"
    factory.assert_not_called()


def test_host_composition_resolves_production_credentials_once(monkeypatch):
    """The shipped composition, its real secret source and real SDK client constructor."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AUTOGRADER_AI_SECRET_NAME", "course-openai")
    lookups = Mock(return_value="secret-key")
    constructed = Mock(side_effect=lambda **options: Mock(
        responses=Mock(parse=Mock(return_value=Mock(output_parsed=openai_provider.AIResponseModel(results=[
            openai_provider.TestOutput(criterion_id="sort", feedback="f", score=70.0),
            openai_provider.TestOutput(criterion_id="sort-again", feedback="f", score=70.0)]))))))
    monkeypatch.setattr("execution_host.openai_provider.fetch_secret", lookups)
    monkeypatch.setattr("execution_host.openai_provider.OpenAI", constructed)
    provider = DockerHost(mode="local").capabilities.ai
    assert [grade_ai(provider).score for _ in range(3)] == [70.0] * 3
    lookups.assert_called_once_with("course-openai", "OPENAI_API_KEY", "us-east-1")
    constructed.assert_called_once()
    options = constructed.call_args.kwargs
    assert options["api_key"] == "secret-key" and options["max_retries"] == 0
    assert options["timeout"].read == openai_provider.REQUEST_TIMEOUT_SECONDS
    assert options["timeout"].connect == openai_provider.CONNECT_TIMEOUT_SECONDS


def test_default_client_has_the_documented_deadline_and_no_retries():
    client = openai_provider.openai_client("k")
    assert client.max_retries == 0
    assert (client.timeout.connect, client.timeout.read, client.timeout.write, client.timeout.pool) == (
        openai_provider.CONNECT_TIMEOUT_SECONDS, *[openai_provider.REQUEST_TIMEOUT_SECONDS] * 3)
    assert openai_provider.REQUEST_TIMEOUT_SECONDS == 180 and openai_provider.CONNECT_TIMEOUT_SECONDS == 10


class FakeSession:
    def __init__(self):
        self.closed = 0

    def prepare_workdir(self, files):
        pass

    def run_process(self, request):
        return ProcessResult(ProcessStatus.EXITED, 0, stdout="5\n")

    def close(self):
        self.closed += 1


@pytest.mark.parametrize("definition, files", [
    (STATIC_DEFINITION, {"index.html": "<main></main>"}),
    (IO_DEFINITION, {"main.py": "print(5)"}),
], ids=["static", "io"])
def test_static_and_io_gradings_never_construct_the_provider(monkeypatch, definition, files):
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    construct = Mock(side_effect=AssertionError("no AI criterion is selected"))
    monkeypatch.setattr("execution_host.openai_provider.OpenAI", construct)
    monkeypatch.setattr("execution_host.openai_provider.fetch_secret", construct)
    host = DockerHost(mode="local")
    monkeypatch.setattr(host, "acquire", lambda language, budget: FakeSession())
    capabilities = HostCapabilities(execution=host.acquire, ai=host.capabilities.ai)
    submission = Submission("s", "s", "a", {name: SubmissionFile(name, text) for name, text in files.items()})
    outcome = build_pipeline(definition=definition, capabilities=capabilities).run(submission).outcome
    assert outcome.status == "completed" and outcome.score == 100
    construct.assert_not_called()


# --- Wire: the real SDK client against a local stub -----------------------------

class Stub(ThreadingHTTPServer):
    """Answers each request with the next scripted reply and logs it first."""
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), StubHandler)
        self.replies = []
        self.requests = []
        self.received = threading.Condition()
        self.release = threading.Event()

    @property
    def url(self):
        return f"http://127.0.0.1:{self.server_address[1]}/v1"

    def wait_for_requests(self, count, timeout=10):
        with self.received:
            assert self.received.wait_for(lambda: len(self.requests) >= count, timeout), self.requests
            return list(self.requests)


class StubHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):  # pylint: disable=invalid-name
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        with self.server.received:
            self.server.requests.append({"path": self.path, "authorization": self.headers["Authorization"],
                                         "body": body})
            reply = self.server.replies.pop(0) if self.server.replies else ("hang",)
            self.server.received.notify_all()
        if reply[0] == "hang":
            self.server.release.wait(30)  # released at teardown; the client has already given up
            return
        status, payload = reply
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


@pytest.fixture
def stub():
    server = Stub()
    thread = threading.Thread(target=server.serve_forever, args=(0.05,), daemon=True)
    thread.start()
    yield server
    server.release.set()
    server.shutdown()
    server.server_close()
    thread.join(10)


def wired(stub, monkeypatch, **deadline):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    return ConfiguredAssessmentProvider(
        api_key="test-key", client_factory=partial(openai_provider.openai_client, base_url=stub.url, **deadline))


def test_valid_structured_response_grades_through_the_real_client(stub, monkeypatch):
    stub.replies = [(200, structured(("sort", 80.0), ("sort-again", 60.0)))] * 2
    provider = wired(stub, monkeypatch)
    outcomes = [grade_ai(provider), grade_ai(provider)]
    for outcome in outcomes:
        assert outcome.status == "completed" and outcome.score == 70.0
        assert {test.id: (test.score, test.report) for test in outcome.tree.base.tests} == {
            "sort": (80.0, "feedback sort"), "sort-again": (60.0, "feedback sort-again")}
    requests = stub.wait_for_requests(2)
    assert len(requests) == 2 and {request["path"] for request in requests} == {"/v1/responses"}
    assert {request["authorization"] for request in requests} == {"Bearer test-key"}


@pytest.mark.parametrize("status", [500, 429, 408, 409, 503])
def test_server_errors_and_rate_limits_make_exactly_one_request(stub, monkeypatch, status):
    stub.replies = [(status, {"error": {"message": "upstream detail", "type": "server_error"}})] * 3
    outcome = grade_ai(wired(stub, monkeypatch))
    assert outcome.status == "failed" and outcome.score is None and outcome.tree is None
    assert (outcome.error.code, outcome.error.category, outcome.error.retryable) == ("PROVIDER_ERROR", "provider", True)
    assert "upstream detail" not in outcome.error.message
    # The grading has returned, so an SDK retry would already be in the log.
    assert len(stub.wait_for_requests(1)) == 1


def test_production_composition_does_not_retry(stub, monkeypatch):
    """The provider the shipped host builds from its environment, over real HTTP."""
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("OPENAI_BASE_URL", stub.url)
    stub.replies = [(500, {"error": {"message": "x"}})] * 3
    outcome = grade_ai(DockerHost(mode="local").capabilities.ai)
    assert outcome.error.code == "PROVIDER_ERROR"
    assert len(stub.wait_for_requests(1)) == 1


def test_unresponsive_provider_fails_within_the_deadline(stub, monkeypatch):
    deadline = 0.5
    provider = wired(stub, monkeypatch, timeout=deadline)
    started = time.monotonic()
    outcome = grade_ai(provider)
    elapsed = time.monotonic() - started
    assert outcome.status == "failed" and outcome.tree is None
    assert (outcome.error.code, outcome.error.retryable) == ("PROVIDER_ERROR", True)
    assert len(stub.wait_for_requests(1)) == 1
    assert deadline <= elapsed < deadline + 5  # one wait, not three; generous margin for a loaded machine


def test_rejected_credential_is_looked_up_again_on_the_next_grading(stub, monkeypatch):
    """Secret rotation: a 401 drops the client; the next grading resolves the new key."""
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    keys = iter(["old-key", "new-key"])
    secrets = Mock(side_effect=lambda *args: next(keys))
    factory = Mock(side_effect=partial(openai_provider.openai_client, base_url=stub.url))
    provider = ConfiguredAssessmentProvider(secret_name="course-openai", secret_source=secrets, client_factory=factory)
    stub.replies = [(401, {"error": {"message": "Incorrect API key", "type": "invalid_request_error"}}),
                    (200, structured(("sort", 100.0), ("sort-again", 100.0))),
                    (200, structured(("sort", 100.0), ("sort-again", 100.0)))]
    rejected = grade_ai(provider)
    assert (rejected.error.code, rejected.error.retryable) == ("PROVIDER_ERROR", True)
    assert [grade_ai(provider).score for _ in range(2)] == [100.0, 100.0]
    assert [request["authorization"] for request in stub.wait_for_requests(3)] == [
        "Bearer old-key", "Bearer new-key", "Bearer new-key"]
    assert secrets.call_count == 2 and factory.call_count == 2
