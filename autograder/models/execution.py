"""Provider-neutral operations accepted by evaluators and owned by a run."""
# Protocol members are documented by their class docstrings.
# pylint: disable=missing-function-docstring
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence
from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.process import ProcessRequest, ProcessResult


@dataclass
class ExtractedFile:
    """An artifact read back from a session's workspace."""
    path: str
    content_bytes: bytes
    size: int
    content_text: str = ""
    encoding: str = "utf-8"


class HttpResponse(Protocol):
    """A response from an assessed server, whatever client the host uses.

    Transport failures are raised as ``OSError`` subclasses (for example
    ``ConnectionError``); an HTTP error status is an ordinary response.
    """
    @property
    def status_code(self) -> int: ...
    @property
    def text(self) -> str: ...
    def json(self) -> Any: ...


class ExecutionSession(Protocol):
    """Workspace operations; fixture/artifact paths are relative to their roots.

    ``run_process`` is the only way to run a process (see ``models/process.py``):
    it returns a ``ProcessResult`` for any process it ran and raises for
    infrastructure failures. ``read_artifact`` raises ``FileNotFoundError`` only
    for a missing file; unknown or invalidated sessions and failed readback raise
    other ``RuntimeError``s.
    """
    fixture_root: str

    def prepare_workdir(self, files: Mapping[str, SubmissionFile]) -> None: ...
    def stage_fixture(self, path: str, content: bytes, read_only: bool) -> None: ...
    def run_process(self, request: ProcessRequest) -> ProcessResult: ...
    def read_artifact(self, path: str) -> ExtractedFile: ...
    def close(self) -> None: ...


class ServerSession(ExecutionSession, Protocol):
    """An assessed server whose startup command/configuration belongs to the host.

    Startup follows staging/setup. Readiness must verify endpoint reachability;
    close must stop the server even when startup or readiness fails.
    """
    def start_server(self) -> None: ...
    def wait_ready(self) -> None: ...
    def stop_server(self) -> None: ...
    def make_request(self, method: str, endpoint: str) -> HttpResponse: ...


@dataclass(frozen=True)
class AssessmentRequest:
    """One prepared AI criterion: its stable criterion ID and evaluator-built prompt."""
    criterion_id: str
    prompt: str


@dataclass(frozen=True)
class ProviderAssessment:
    """A provider's answer for exactly one requested criterion ID."""
    criterion_id: str
    score: float
    report: str = ""


class AssessmentProvider(Protocol):
    """A host-supplied AI provider (model, credentials and deadline are host-owned).

    ``assess`` receives one batch of requests and returns one assessment per
    request. The engine validates exact criterion-ID coverage and every score;
    providers must not retry, drop or invent criteria.
    """
    def assess(self, requests: Sequence[AssessmentRequest], *, context_files: Mapping[str, str],
               locale: str) -> Sequence[ProviderAssessment]: ...
