"""Operations supplied by a host, with one owned session per execution.

Providers are borrowed and may be shared. A returned execution session transfers
ownership immediately: the pipeline closes it once, including staging failures.
"""
from dataclasses import dataclass
from typing import Callable

from autograder.models.contracts.definition import CompiledDefinition, LanguagePreparation
from sandbox_manager.models.sandbox_models import Language
from autograder.models.execution import AssessmentProvider, ExecutionSession, ServerSession


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
    from autograder.models.contracts.catalog import required_capabilities
    selected = {id(test.test_function) for category in (
        compiled.criteria_tree.base, compiled.criteria_tree.bonus, compiled.criteria_tree.penalty
    ) if category for test in category.get_all_tests()}
    capabilities = set()
    for template in compiled.templates:
        for function in template.get_tests().values():
            if id(function) in selected:
                capabilities.update(required_capabilities(template, function))
    preparation = compiled.definition.preparation.languages.get(language.value, LanguagePreparation())
    if preparation.setup_commands or compiled.definition.preparation.fixtures:
        capabilities.add("sandbox_execution")
    if compiled.definition.preparation.fixtures:
        capabilities.add("fixture_provider")
    return ExecutionRequirements(frozenset(capabilities), preparation)
