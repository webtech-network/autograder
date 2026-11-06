"""Operations supplied by a host, with one owned session per execution.

Providers are borrowed and may be shared. A returned execution session transfers
ownership immediately: the pipeline closes it once, including staging failures.
"""
from dataclasses import dataclass
from typing import Callable

from autograder.models.contracts.definition import CompiledDefinition, LanguagePreparation
from autograder.models.evaluation_error import EvaluationError
from autograder.models.language import Language
from autograder.models.execution import AssessmentProvider, ExecutionSession, ServerSession

#: Process deadline of each preparation setup command.
SETUP_TIMEOUT_SECONDS = 30
#: What a session needs beyond its processes' deadlines: starting and collecting
#: each process, and staging files and fixtures plus cleanup once per session.
PROCESS_ALLOWANCE_SECONDS = 2
SESSION_ALLOWANCE_SECONDS = 60


class FixtureNotFound(LookupError):
    """Raised by a fixture provider when a logical reference has no content.

    A fixture provider maps a reference to bytes; ``b""`` is valid content.
    Any other exception is a provider failure (the reference may exist).
    """


@dataclass(frozen=True)
class ExecutionBudget:
    """Worst-case time one grading needs, derived only from deadlines already declared.

    ``process_seconds`` sums the deadline of every process the selected criteria
    and the language's setup commands may run (``processes`` of them);
    ``ai_calls`` counts provider calls (one batch for all AI criteria). No
    authoring field sets it.
    """
    process_seconds: float = 0.0
    processes: int = 0
    ai_calls: int = 0

    @property
    def session_seconds(self) -> float:
        """The lifetime an execution session must be granted, counted from its grant."""
        return self.process_seconds + self.processes * PROCESS_ALLOWANCE_SECONDS + SESSION_ALLOWANCE_SECONDS


@dataclass(frozen=True)
class HostCapabilities:
    """What a host supplies. ``execution(language, budget)`` opens a session that
    lives at least ``budget.session_seconds``; ``max_session_seconds`` is the
    longest session the host grants (``None``: the host states no maximum)."""
    execution: Callable[[Language, ExecutionBudget], ExecutionSession] | None = None
    fixtures: Callable[[str], bytes] | None = None
    ai: AssessmentProvider | None = None
    server_execution: Callable[[Language, ExecutionBudget], ServerSession] | None = None
    max_session_seconds: float | None = None


@dataclass(frozen=True)
class ExecutionRequirements:
    capabilities: frozenset[str]
    preparation: LanguagePreparation
    budget: ExecutionBudget = ExecutionBudget()


def requirements_for(compiled: CompiledDefinition, language: Language) -> ExecutionRequirements:
    """Use the same evaluator declaration as discovery, only for selected tests."""
    capabilities = set()
    deadlines = []
    ai_calls = 0
    for test in compiled.criteria_tree.get_all_tests():
        capabilities.update(test.capabilities)
        if "sandbox_execution" in test.capabilities:
            deadlines.extend(test.test_function.process_timeouts)
        if "ai_provider" in test.capabilities:
            ai_calls = 1  # every selected AI criterion shares one provider call
    definition = compiled.definition
    preparation = definition.preparation.languages.get(language.value, LanguagePreparation())
    deadlines.extend(SETUP_TIMEOUT_SECONDS for _ in preparation.setup_commands)
    if preparation.setup_commands or definition.preparation.fixtures:
        capabilities.add("sandbox_execution")
    if definition.preparation.fixtures:
        capabilities.add("fixture_provider")
    budget = ExecutionBudget(float(sum(deadlines)), len(deadlines), ai_calls)
    return ExecutionRequirements(frozenset(capabilities), preparation, budget)


def check_budget(budget: ExecutionBudget, max_session_seconds: float | None) -> None:
    """Refuse, before anything runs, a session longer than the host grants (not retryable)."""
    if max_session_seconds is not None and budget.session_seconds > max_session_seconds:
        raise EvaluationError("EXECUTION_BUDGET_EXCEEDED",
                              "The definition needs more execution time than this host grants.", "capability")
