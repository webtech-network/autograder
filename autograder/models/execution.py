"""Provider-neutral operations accepted by evaluators and owned by a run."""
from typing import Mapping, Protocol
from autograder.models.dataclass.submission import SubmissionFile
from autograder.models.dataclass.test_result import TestResult
from autograder.models.process import ProcessRequest, ProcessResult
from sandbox_manager.models.sandbox_models import ExtractedFile, HttpResponse


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


class AssessmentProvider(Protocol):
    def run(self, tests, submission_files: dict[str, str], locale: str = "en") -> dict[str, TestResult]: ...
