"""Public base for evaluators that run the student's program.

It lives outside ``autograder.template_library`` so that ``import autograder``
(which exports it) never builds the built-in templates.
"""
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from autograder.models.abstract.test_function import EvaluationInput, ParameterIssue, TestFunction
from autograder.models.dataclass.test_result import TestResult
from autograder.models.evaluation_error import EvaluationError
from autograder.models.execution import ExecutionSession
from autograder.models.language import Language
from autograder.models.process import (
    SHELL_OPERATOR_MESSAGE, WORKSPACE, ProcessRequest, ProcessResult, ProcessStatus, SandboxExhausted, lines_to_stdin,
    shell_operator, split_command,
)
from autograder.translations import t

#: The ``CMD`` placeholder: the conventional entry point of each runtime. This is
#: the only default-command table. A language without an entry cannot use ``CMD``
#: (``MISSING_LANGUAGE_COMMAND`` at compilation); authors can always write an
#: explicit command or a language map instead.
DEFAULT_COMMANDS: Dict[Language, str] = {
    Language.PYTHON: "python3 main.py",
    Language.JAVA: "java Main",
    Language.NODE: "node index.js",
    Language.CPP: "./a.out",
    Language.C: "./a.out",
}
DEFAULT_COMMAND = "CMD"

#: Process deadline of one assessed run (see ProcessRequest.timeout).
RUN_TIMEOUT_SECONDS = 30


def in_workspace(executable: str) -> bool:
    """Whether an executable is a path into the submission's workspace (``./a.out``, ``bin/app``).

    The workspace belongs to the submission, so such a program that is missing
    or not executable is the submission's result. A bare command is looked up
    in the runtime image's ``PATH``, and an absolute path outside the workspace
    is part of the image: when those cannot start, the host lacks a capability.
    """
    if executable.startswith("/"):
        return executable.startswith(f"{WORKSPACE}/")
    return "/" in executable


class BaseExecutionTest(TestFunction):  # pylint: disable=abstract-method
    """Public base for evaluators that run the student's program (``from autograder import BaseExecutionTest``).

    It declares ``sandbox_execution`` and needs every submitted file. Subclasses
    call ``run_program`` (the bound language's command, exact stdin lines, one
    deadline) and ``assessed_failure`` (a timeout or nonzero exit is an assessed
    zero). A ``program_command`` parameter is checked at compilation: quoting,
    no shell operators, and language-map/``CMD`` coverage of every allowed language.
    """

    uses_context_files = True
    required_capabilities = ("sandbox_execution",)

    def validate_parameters(self, parameters: Dict[str, Any], *,
                            languages: Tuple[str, ...]) -> Iterable[ParameterIssue]:
        """Each command is a well-quoted argument vector without shell operators, and a
        language map or ``CMD`` names a command for every allowed language."""
        command = parameters.get("program_command")
        if command is None:
            return
        candidates = command.items() if isinstance(command, dict) else ((None, command),)
        for key, text in candidates:
            if text == DEFAULT_COMMAND:
                continue
            path = ("program_command",) if key is None else ("program_command", key)
            try:
                split_command(text)
            except ValueError:
                yield ParameterIssue("INVALID_COMMAND", path,
                                     "Command quoting is malformed; use explicit sh -c '...' for shell syntax")
                continue
            operator = shell_operator(text)
            if operator is not None:
                yield ParameterIssue("SHELL_OPERATOR", path, SHELL_OPERATOR_MESSAGE.format(operator=operator))
        if isinstance(command, dict):
            covered = set(command)
        elif command == DEFAULT_COMMAND:
            covered = {language.value for language in DEFAULT_COMMANDS}
        else:
            return
        if not set(languages).issubset(covered):
            yield ParameterIssue("MISSING_LANGUAGE_COMMAND", ("program_command",),
                                 "Command map must cover every allowed language")

    @staticmethod
    def resolve_command(program_command: Any, evaluation: EvaluationInput) -> str:
        """The command for the bound submission language.

        A plain string is used verbatim; a language map and ``CMD`` select by
        ``evaluation.language``. Compilation guarantees coverage, so a missing
        entry here means the evaluator was invoked outside a compiled plan.
        """
        if isinstance(program_command, str) and program_command != DEFAULT_COMMAND:
            return program_command
        if evaluation.language is None:
            raise EvaluationError("LANGUAGE_REQUIRED", "A language is required to select the program command.", "submission")
        table = program_command if isinstance(program_command, dict) else {
            language.value: command for language, command in DEFAULT_COMMANDS.items()}
        try:
            return table[evaluation.language.value]
        except KeyError:
            raise EvaluationError("MISSING_LANGUAGE_COMMAND", "No program command is defined for this language.",
                                  "submission") from None

    @staticmethod
    def require_session(evaluation: EvaluationInput) -> ExecutionSession:
        """The execution session bound to this evaluator by its capability declaration."""
        if evaluation.session is None:
            raise EvaluationError("CAPABILITY_UNAVAILABLE", "The execution environment is unavailable.", "capability")
        return evaluation.session

    def run_program(self, evaluation: EvaluationInput, program_command: Any,
                    inputs: Optional[List[str]] = None) -> Union[ProcessResult, TestResult]:
        """Run the program once with the process contract.

        ``inputs`` are lines: each is sent followed by a newline and nothing else is
        sent, so ``[]`` is empty stdin. The command is an argument vector; shell
        syntax needs an explicit ``sh -c``. Infrastructure failures and a runtime
        command that cannot be started are execution errors, never an assessed
        zero. What the submission did to its own sandbox is assessed and returned
        as the zero ``TestResult``: an entry point in the workspace that is
        missing or not executable, or an exhausted memory or process limit.
        """
        session = self.require_session(evaluation)
        try:
            request = ProcessRequest.command(self.resolve_command(program_command, evaluation),
                                             stdin=lines_to_stdin(inputs or []), timeout=RUN_TIMEOUT_SECONDS)
        except ValueError as e:  # compilation rejects these; reached only outside a compiled plan
            raise EvaluationError("INVALID_COMMAND", "The program command is not valid.", "definition") from e
        locale = evaluation.locale
        try:
            result = session.run_process(request)
        except SandboxExhausted:
            return TestResult(test_name=self.name, score=0.0, report=t("io.execution.exhausted", locale=locale))
        except (ValueError, TimeoutError, RuntimeError) as e:
            raise EvaluationError("SANDBOX_ERROR", "The execution environment could not complete evaluation.",
                                  "capability", True) from e
        if result.status is ProcessStatus.NOT_STARTED:
            if not in_workspace(result.missing_executable or ""):
                raise EvaluationError("PROCESS_START_FAILED", "The assessed program could not be started.",
                                      "capability")
            return TestResult(test_name=self.name, score=0.0,
                              report=t("io.execution.not_started", locale=locale, program=result.missing_executable))
        return result

    def assessed_failure(self, result: Union[ProcessResult, TestResult],
                         locale: Optional[str] = None) -> Optional[TestResult]:
        """A zero for a program that timed out or returned a nonzero exit code.

        Classification uses only the exit status, never the wording of stderr.
        An already assessed ``run_program`` result is returned as it is.
        """
        if isinstance(result, TestResult):
            return result
        if result.status is ProcessStatus.TIMED_OUT:
            return TestResult(test_name=self.name, score=0.0,
                              report=t("io.execution.timeout", locale=locale, time=result.duration))
        if result.exit_code != 0:
            error = result.stderr if result.stderr.strip() else t(
                "io.execution.exit_code", locale=locale, code=result.exit_code)
            return TestResult(test_name=self.name, score=0.0,
                              report=t("io.execution.runtime_error", locale=locale, error=error))
        return None

    @staticmethod
    def _normalize(text: str) -> str:
        """
        Normalize text for output comparison by:
        1. Converting all line endings to \n
        2. Removing trailing whitespace from each line
        3. Removing leading and trailing whitespace from the entire output
        """
        lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        return "\n".join(line.rstrip() for line in lines).strip()
