"""Supported Python facade for definitions, discovery and terminal results."""
from autograder.autograder import build_pipeline
from autograder.models.capabilities import HostCapabilities
from autograder.models.execution import ExecutionSession, ServerSession, AssessmentProvider
from autograder.models.contracts.definition import (
    CompiledDefinition, DefinitionValidationError, GradingDefinition,
    compile_definition, grading_definition_json_schema, select_language,
)
from autograder.models.contracts.outcome import validate_outcome, outcome_json_schema
from autograder.models.contracts.catalog import describe_templates
from autograder.facade import evaluate_submission
from autograder.models.abstract.template import Template
from autograder.models.abstract.test_function import TestFunction
from autograder.models.dataclass.submission import Submission, SubmissionFile
from autograder.models.dataclass.test_result import TestResult

__all__ = ["build_pipeline", "compile_definition", "select_language", "validate_outcome",
           "grading_definition_json_schema", "outcome_json_schema", "GradingDefinition",
           "CompiledDefinition", "DefinitionValidationError", "describe_templates",
           "evaluate_submission", "Template", "TestFunction", "Submission",
           "SubmissionFile", "TestResult", "HostCapabilities", "ExecutionSession",
           "ServerSession", "AssessmentProvider"]
