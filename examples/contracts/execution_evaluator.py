"""Execution evaluator example; run with ``python -m examples.contracts.execution_evaluator``.

An evaluator that runs the submission is still a local change: its
implementation, its parameter contract and its registration. The only
differences from a static evaluator are that it declares
``required_capabilities = ("sandbox_execution",)`` and uses the session it then
receives in ``evaluation.session``.

This example teaches those semantics with a *fake* execution capability, so it
needs no Docker. A real host supplies the same ``HostCapabilities.execution``
callable (``execution_host.docker.DockerHost`` for the shipped hosts); see
"Host composition" in docs/architecture/extending.md.
"""
# The keyword-only parameters of ``execute`` are the evaluator's contract, so the
# override intentionally differs from the base signature.
# pylint: disable=arguments-differ
from typing import Annotated, Any, Dict, Iterable, List, Tuple

from pydantic import Field

from autograder import (
    EvaluationInput, HostCapabilities, ParameterIssue, Submission, SubmissionFile, Template,
    TestFunction, TestResult, compile_definition, evaluate_submission,
)
from autograder.models.evaluation_error import EvaluationError
from autograder.models.process import (
    ProcessRequest, ProcessResult, ProcessStatus, lines_to_stdin, split_command,
)


# --- 1. Implementation and 2. parameter contract -----------------------------

class PrintsLine(TestFunction):
    """Run the program once and look for one exact line of standard output."""
    name = "prints_line"
    description = "Run the program with the given input lines and check one output line."
    #: Declaring the capability is what makes the pipeline acquire a session
    #: and hand it to this evaluator. Undeclared evaluators receive ``None``.
    required_capabilities = ("sandbox_execution",)
    #: The program may import any submitted file, so it needs all of them.
    uses_context_files = True

    def validate_parameters(self, parameters: Dict[str, Any], *,
                            languages: Tuple[str, ...]) -> Iterable[ParameterIssue]:
        """Pure compile-time check that a JSON contract cannot express."""
        del languages
        try:
            split_command(parameters["command"])
        except ValueError:
            yield ParameterIssue("INVALID_COMMAND", ("command",), "Command quoting is malformed")

    def execute(self, evaluation: EvaluationInput, *,
                command: Annotated[str, Field(min_length=1, description="Program command (argv, no shell)")],
                inputs: Annotated[List[str], Field(description="Lines sent to standard input")],
                expected_line: Annotated[str, Field(description="A line the program must print")]) -> TestResult:
        result = evaluation.session.run_process(
            ProcessRequest.command(command, stdin=lines_to_stdin(inputs), timeout=10))
        if result.status is ProcessStatus.NOT_STARTED:
            # The host could not start the program: not a student zero.
            raise EvaluationError("PROCESS_START_FAILED", "The program could not be started.", "capability")
        if result.status is ProcessStatus.TIMED_OUT:
            return TestResult(self.name, 0, "The program did not finish in time.")
        if expected_line in result.stdout.splitlines():
            return TestResult(self.name, 100, "Expected line printed.")
        return TestResult(self.name, 0, f"Exit {result.exit_code}; expected line missing.")


# --- 3. Registration -----------------------------------------------------------

class ProgramTemplate(Template):
    """A trusted registry holding one execution evaluator."""
    template_name = "Program checks"
    template_description = "One trusted execution evaluator"
    requires_sandbox = True

    def __init__(self):
        self.tests = {"prints_line": PrintsLine()}


DEFINITION = {
    "schema_version": "1.0",
    "templates": ["program_checks"],
    "languages": ["python"],
    "criteria": {"base": {"weight": 100, "tests": [{
        "id": "greets", "type": "prints_line", "name": "Greets the user",
        "parameters": {"command": "python3 main.py", "inputs": ["Ada"], "expected_line": "Hello, Ada"},
    }]}},
}


# --- A fake execution capability (teaching and tests only) ---------------------

class FakeSession:
    """Implements the ``ExecutionSession`` protocol without running anything.

    It records what the evaluator asked for and answers every process with the
    scripted ``ProcessResult``. Real sessions run the request in a sandbox.
    """
    fixture_root = "/fixtures"

    def __init__(self, result: ProcessResult):
        self.result = result
        self.files: Dict[str, SubmissionFile] = {}
        self.requests: List[ProcessRequest] = []
        self.closed = 0

    def prepare_workdir(self, files):
        """Record the files the run staged."""
        self.files = dict(files)

    def stage_fixture(self, path, content, read_only):
        """This definition declares no fixtures."""
        raise AssertionError("This definition stages no fixtures")

    def run_process(self, request: ProcessRequest) -> ProcessResult:
        """Record the request and answer with the scripted result."""
        self.requests.append(request)
        return self.result

    def read_artifact(self, path):
        """No artifacts exist in the fake workspace."""
        raise FileNotFoundError(path)

    def close(self):
        """Count closes; the run must close its owned session exactly once."""
        self.closed += 1


def fake_capabilities(result: ProcessResult, sessions: List[FakeSession]) -> HostCapabilities:
    """``execution`` is called once per run with the bound language; the run owns
    and closes the returned session."""
    def acquire(language):
        """Open one owned session for the bound language."""
        del language
        session = FakeSession(result)
        sessions.append(session)
        return session
    return HostCapabilities(execution=acquire)


def grade(program: str, result: ProcessResult, sessions: List[FakeSession] | None = None):
    """Grade ``program`` with a fake session that answers every process with ``result``."""
    compiled = compile_definition(DEFINITION, templates={"program_checks": ProgramTemplate()})
    submission = Submission("local", "local", "execution-example",
                            {"main.py": SubmissionFile("main.py", program)})
    return evaluate_submission(submission, definition=compiled,
                               capabilities=fake_capabilities(result, [] if sessions is None else sessions))


if __name__ == "__main__":
    opened: List[FakeSession] = []
    outcome = grade("print('Hello, ' + input())",
                    ProcessResult(ProcessStatus.EXITED, 0, stdout="Hello, Ada\n"), opened)
    print(outcome.model_dump_json(indent=2))
    print("argv:", opened[0].requests[0].argv, "stdin:", opened[0].requests[0].stdin, "closed:", opened[0].closed)
    if outcome.status != "completed" or outcome.score != 100:
        raise SystemExit(1)
