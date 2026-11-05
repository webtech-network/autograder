"""Validate inputs without resources, then prepare the host-owned session."""
from autograder.models.capabilities import ExecutionRequirements, FixtureNotFound, HostCapabilities
from autograder.models.contracts.definition import CompiledDefinition
from autograder.models.dataclass.submission import Submission
from autograder.models.evaluation_error import EvaluationError
from autograder.models.execution import ExecutionSession
from autograder.services.file_selection import select_files
from autograder.models.process import ProcessRequest, ProcessStatus, SandboxExhausted

SETUP_TIMEOUT_SECONDS = 30


def validate_submission(compiled: CompiledDefinition, submission: Submission, requirements: ExecutionRequirements) -> None:
    """Check required inputs before calling any host capability."""
    missing = set(requirements.preparation.required_files) - set(submission.submission_files)
    if missing:
        raise EvaluationError("REQUIRED_FILE_MISSING", "A required submission file is missing.", "submission")
    for test in compiled.criteria_tree.get_all_tests():
        select_files(test, submission.submission_files, submission.evaluation_scope, submission.language)


def check_capabilities(required: frozenset[str], providers: HostCapabilities) -> None:
    """Reject unavailable selected capabilities without acquiring resources."""
    if "http_network" in required and providers.server_execution is None:
        raise EvaluationError("SERVER_CAPABILITY_UNAVAILABLE", "This host cannot start and reach an assessed server.", "capability")
    if "sandbox_execution" in required and "http_network" not in required and providers.execution is None:
        raise EvaluationError("CAPABILITY_UNAVAILABLE", "The execution environment is unavailable.", "capability")
    if "fixture_provider" in required and providers.fixtures is None:
        raise EvaluationError("FIXTURE_PROVIDER_UNAVAILABLE", "The fixture provider is unavailable.", "capability")
    if "ai_provider" in required and providers.ai is None:
        raise EvaluationError("PROVIDER_UNAVAILABLE", "The assessment provider is unavailable.", "provider")


def prepare_session(
    session: ExecutionSession, compiled: CompiledDefinition,
    requirements: ExecutionRequirements, providers: HostCapabilities,
) -> None:
    """Stage fixtures and setup commands, then start an assessed server if needed."""
    try:
        for fixture in compiled.definition.preparation.fixtures:
            content = providers.fixtures(fixture.reference)
            if not isinstance(content, bytes):
                raise TypeError("Fixture providers must return bytes")
            session.stage_fixture(fixture.path, content, fixture.read_only)
        for command in requirements.preparation.setup_commands:
            # Same process contract as assessment: argv (no implicit shell), empty stdin.
            result = session.run_process(ProcessRequest.command(command.command, timeout=SETUP_TIMEOUT_SECONDS))
            if result.status is ProcessStatus.NOT_STARTED:
                raise EvaluationError("PREPARATION_ERROR", "A setup command could not be started.", "capability")
            if not result.succeeded:
                raise EvaluationError("PREPARATION_FAILED", "A required setup command failed.", "submission")
        if "http_network" in requirements.capabilities:
            session.start_server()
            session.wait_ready()
    except EvaluationError:
        raise
    except SandboxExhausted as exc:
        # A setup command (for example the compiler) exhausted the sandbox on the submission.
        raise EvaluationError("PREPARATION_FAILED", "A required setup command failed.", "submission") from exc
    except FixtureNotFound as exc:
        # Same safe outcome as other fixture failures, but retrying cannot help.
        raise EvaluationError("PREPARATION_ERROR", "Assignment preparation could not complete.", "capability", False) from exc
    except Exception as exc:
        raise EvaluationError("PREPARATION_ERROR", "Assignment preparation could not complete.", "capability", True) from exc
