"""Grading entry point that exposes only the finalized integration artifact."""
from typing import Mapping

from autograder.autograder import build_pipeline
from autograder.models.abstract.template import Template
from autograder.models.contracts.definition import CompiledDefinition, GradingDefinition
from autograder.models.contracts.outcome import TerminalOutcome
from autograder.models.contracts.provenance import DefinitionProvenance
from autograder.models.dataclass.submission import Submission


def evaluate_submission(
    submission: Submission,
    *,
    definition: GradingDefinition | dict | CompiledDefinition,
    templates: Mapping[str, Template] | None = None,
    provenance: DefinitionProvenance | None = None,
    capabilities=None,
) -> TerminalOutcome:
    """Compile, evaluate and clean up before returning an immutable outcome.

    Invalid definitions raise DefinitionValidationError; execution failures return
    failed outcomes. Templates are trusted, already-instantiated Python objects.
    Hosts explicitly supply capabilities; static evaluation needs none. Returned
    sessions belong to the run and are closed before the immutable outcome returns.
    """
    return build_pipeline(
        definition=definition, templates=templates, provenance=provenance,
        locale=submission.locale, capabilities=capabilities,
    ).run(submission).outcome
