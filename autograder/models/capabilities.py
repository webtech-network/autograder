"""Operations supplied by a host, with one owned session per execution.

Providers are borrowed and may be shared. A returned execution session transfers
ownership immediately: the pipeline closes it once, including staging failures.
"""
from dataclasses import dataclass
from typing import Callable

from autograder.models.contracts.definition import CompiledDefinition, LanguagePreparation
from sandbox_manager.models.sandbox_models import Language
from autograder.models.execution import AssessmentProvider, ExecutionSession, ServerSession


class FixtureNotFound(LookupError):
    """Raised by a fixture provider when a logical reference has no content.

    A fixture provider maps a reference to bytes; ``b""`` is valid content.
    Any other exception is a provider failure (the reference may exist).
    """


@dataclass(frozen=True)
class HostCapabilities:
    execution: Callable[[Language], ExecutionSession] | None = None
    fixtures: Callable[[str], bytes] | None = None
    ai: AssessmentProvider | None = None
    server_execution: Callable[[Language], ServerSession] | None = None


@dataclass(frozen=True)
class ExecutionRequirements:
    capabilities: frozenset[str]
    preparation: LanguagePreparation


def requirements_for(compiled: CompiledDefinition, language: Language) -> ExecutionRequirements:
    """Use the same evaluator declaration as discovery, only for selected tests."""
    capabilities = set()
    for test in compiled.criteria_tree.get_all_tests():
        capabilities.update(test.capabilities)
    definition = compiled.definition
    preparation = definition.preparation.languages.get(language.value, LanguagePreparation())
    if preparation.setup_commands or definition.preparation.fixtures:
        capabilities.add("sandbox_execution")
    if definition.preparation.fixtures:
        capabilities.add("fixture_provider")
    return ExecutionRequirements(frozenset(capabilities), preparation)
