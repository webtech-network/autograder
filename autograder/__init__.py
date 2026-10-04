"""Small public Python interface for grading definitions and terminal results."""
from autograder.autograder import build_pipeline
from autograder.models.contracts.definition import (
    CompiledDefinition, DefinitionValidationError, GradingDefinition,
    compile_definition, grading_definition_json_schema, select_language,
)
from autograder.models.contracts.outcome import validate_outcome, outcome_json_schema

__all__ = ["build_pipeline", "compile_definition", "select_language", "validate_outcome",
           "grading_definition_json_schema", "outcome_json_schema", "GradingDefinition",
           "CompiledDefinition", "DefinitionValidationError"]
