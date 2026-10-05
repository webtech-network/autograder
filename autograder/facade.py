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
) -> TerminalOutcome:
    """Compile, evaluate and clean up before returning an immutable outcome.

    Invalid definitions raise DefinitionValidationError; execution failures return
    failed outcomes. Templates are trusted, already-instantiated Python objects.
    Sandbox/provider resources use the current host configuration; discovery does
    not provision them or guarantee availability. Explicit provider injection is
    tracked separately in INT-14.
    """
    return build_pipeline(
        definition=definition, templates=templates, provenance=provenance,
        locale=submission.locale,
    ).run(submission).outcome
