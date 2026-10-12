"""Evaluate selected AI criteria once and return assessments by criterion ID."""
from autograder.models.abstract.ai_test_function import AiTestFunction
from autograder.models.criteria_tree import CriteriaTree
from autograder.models.dataclass.submission import Submission
from autograder.models.dataclass.test_result import TestResult
from autograder.models.evaluation_error import EvaluationError
from autograder.models.execution import AssessmentProvider
from autograder.services.file_selection import select_files
from autograder.utils.executors.ai_executor import TestInput


def evaluate_ai_batch(
    criteria: CriteriaTree, submission: Submission, provider: AssessmentProvider,
) -> dict[str, TestResult]:
    """Build one batch and require exact criterion-ID coverage from the provider."""
    inputs = []
    context_files = [submission.submission_files[name] for name in sorted(submission.submission_files)]
    for category in (criteria.base, criteria.bonus, criteria.penalty):
        if category is None:
            continue
        for test in category.get_all_tests():
            if not isinstance(test.test_function, AiTestFunction):
                continue
            files = select_files(test, submission.submission_files, submission.evaluation_scope, submission.language)
            prompt = test.test_function.build_prompt(
                files, locale=submission.locale, context_files=context_files, **test.parameters,
            )
            inputs.append(TestInput(test_name=test.criterion_id, prompt=prompt))
    if not inputs:
        return {}
    results = provider.run(inputs, {file.filename: file.content for file in context_files}, submission.locale)
    if set(results) != {item.test_name for item in inputs}:
        raise EvaluationError("MISSING_EVALUATOR_RESULT", "A required AI assessment was not returned.", "provider", True)
    return results
