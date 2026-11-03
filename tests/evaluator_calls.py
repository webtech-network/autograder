"""Invoke evaluators exactly as the grader does, for focused unit tests."""
from autograder.models.abstract.ai_test_function import AiTestFunction
from autograder.models.abstract.test_function import EvaluationInput
from sandbox_manager.models.sandbox_models import Language


def invoke(function, files=None, sandbox=None, *, submission_language=None, locale="en", **parameters):
    """Validate ``parameters`` through the evaluator contract, then call its entry point.

    Like compilation, the contract rejects invalid values and supplies defaults;
    the evaluator receives the normalized values and a typed runtime input.
    """
    normalized = function.config_schema.model_validate(parameters, strict=True, extra="forbid").model_dump(mode="json")
    language = None if submission_language is None else Language(getattr(submission_language, "value", submission_language))
    evaluation = EvaluationInput(files=tuple(files or ()), language=language, locale=locale or "en", session=sandbox)
    if isinstance(function, AiTestFunction):
        return function.build_prompt(evaluation, **normalized)
    return function.execute(evaluation, **normalized)
