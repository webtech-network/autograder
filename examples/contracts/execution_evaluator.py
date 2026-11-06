"""Execution evaluator example; run with ``python -m examples.contracts.execution_evaluator``.

An evaluator that runs the submission is still a local change: its
implementation, its parameter contract and its registration. It subclasses the
public ``BaseExecutionTest``, which declares ``sandbox_execution`` (so the run
acquires a session and hands it to this evaluator in ``evaluation.session``) and
supplies the shared steps: ``run_program`` runs the bound language's command with
exact stdin and a deadline, and ``assessed_failure`` turns a timeout or nonzero
exit into an assessed zero (as it does a missing workspace program or an
exhausted sandbox, which ``run_program`` already assessed). A runtime command
that cannot start fails the run instead.

Everything here is imported from ``autograder``. This example teaches those
semantics with a *fake* execution capability, so it needs no Docker. A real host
supplies the same ``HostCapabilities.execution`` callable
(``execution_host.docker.DockerHost`` for the shipped hosts); see "Host
composition" in docs/architecture/extending.md.
"""
# The keyword-only parameters of ``execute`` are the evaluator's contract, so the
# override intentionally differs from the base signature.
# pylint: disable=arguments-differ
from typing import Annotated, Dict, List

from pydantic import Field

from autograder import (
    BaseExecutionTest, EvaluationInput, HostCapabilities, ProcessRequest, ProcessResult, ProcessStatus,
    Submission, SubmissionFile, Template, TestResult, compile_definition, evaluate_submission,
)


# --- 1. Implementation and 2. parameter contract -----------------------------

class PrintsLine(BaseExecutionTest):
    """Run the program once and look for one exact line of standard output."""
    name = "prints_line"
    description = "Run the program with the given input lines and check one output line."

    def execute(self, evaluation: EvaluationInput, *,
                program_command: Annotated[str, Field(min_length=1, description="Program command (argv, no shell)")],
                inputs: Annotated[List[str], Field(description="Lines sent to standard input")],
                expected_line: Annotated[str, Field(description="A line the program must print")]) -> TestResult:
        # Compilation already rejected malformed quoting in ``program_command``
        # (the base class's ``validate_parameters``).
        result = self.run_program(evaluation, program_command, inputs)
        failure = self.assessed_failure(result, evaluation.locale)
        if failure:
            return failure
        if expected_line in result.stdout.splitlines():
            return TestResult(self.name, 100, "Expected line printed.")
        return TestResult(self.name, 0, "Expected line missing.")


# --- 3. Registration -----------------------------------------------------------

TEMPLATE = Template("Program checks", "One trusted execution evaluator", [PrintsLine()])


DEFINITION = {
    "schema_version": "1.0",
    "templates": ["program_checks"],
    "languages": ["python"],
    "criteria": {"base": {"weight": 100, "tests": [{
        "id": "greets", "type": "prints_line", "name": "Greets the user",
        "parameters": {"program_command": "python3 main.py", "inputs": ["Ada"], "expected_line": "Hello, Ada"},
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

    def stage_fixtures(self, fixtures):
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
    compiled = compile_definition(DEFINITION, templates={"program_checks": TEMPLATE})
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
