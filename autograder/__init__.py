"""Supported Python facade for definitions, discovery and terminal results."""
#: The release version, as ``pyproject.toml`` declares it (``tests/unit/test_release.py`` keeps them equal).
__version__ = "1.0.0"

from autograder.autograder import build_pipeline
from autograder.models.capabilities import HostCapabilities
from autograder.models.execution import (
    AssessmentProvider, AssessmentRequest, ExecutionSession, ProviderAssessment, ServerSession,
)
from autograder.models.contracts.definition import (
    CompiledDefinition, DefinitionValidationError, GradingDefinition,
    compile_definition, compile_snapshot, grading_definition_json_schema, select_language,
)
from autograder.models.contracts.outcome import validate_outcome, outcome_json_schema, outcome_score_vector
from autograder.models.contracts.comparison import ComparisonError, OutcomeComparison, compare_outcomes
from autograder.models.contracts.catalog import describe_templates
from autograder.facade import evaluate_submission
from autograder.models.abstract.template import Template
from autograder.models.abstract.test_function import EvaluationInput, ParameterIssue, TestFunction
from autograder.models.abstract.ai_test_function import AiTestFunction
from autograder.models.dataclass.submission import Submission, SubmissionFile
from autograder.models.dataclass.test_result import TestResult
from autograder.models.language import Language
from autograder.models.locale import Locale
from autograder.models.evaluation_error import EvaluationError
from autograder.models.process import ProcessRequest, ProcessResult, ProcessStatus, lines_to_stdin, split_command
from autograder.models.abstract.execution_test import BaseExecutionTest

__all__ = ["build_pipeline", "compile_definition", "compile_snapshot", "select_language", "validate_outcome",
           "grading_definition_json_schema", "outcome_json_schema", "GradingDefinition",
           "CompiledDefinition", "DefinitionValidationError", "describe_templates",
           "evaluate_submission", "Template", "TestFunction", "AiTestFunction",
           "EvaluationInput", "ParameterIssue", "Submission",
           "SubmissionFile", "TestResult", "HostCapabilities", "ExecutionSession",
           "ServerSession", "AssessmentProvider", "AssessmentRequest", "ProviderAssessment",
           "outcome_score_vector", "compare_outcomes", "OutcomeComparison", "ComparisonError", "Language",
           "Locale",
           # Evaluator authoring: failure type, process contract and the shared run-the-program base.
           "EvaluationError", "ProcessRequest", "ProcessResult", "ProcessStatus", "lines_to_stdin",
           "split_command", "BaseExecutionTest"]
