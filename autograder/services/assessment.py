"""Assess every selected criterion once and return results keyed by criterion ID.

Each criterion is prepared once: the shared file-selection policy chooses its
files and it receives an isolated copy of its canonical parameters. Ordinary
evaluators then run individually. AI evaluators are assessed together by
``assess_many``, one provider call for the whole group (a single AI criterion
is a group of one). Both paths share result validation, and scoring consumes
only the merged ID-keyed results; no evaluator ever receives another
criterion's result.
"""
import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from autograder.models.abstract.ai_test_function import AiTestFunction
from autograder.models.abstract.test_function import EvaluationInput
from autograder.models.criteria_tree import CriteriaTree, TestNode
from autograder.models.dataclass.submission import Submission
from autograder.models.dataclass.test_result import TestResult
from autograder.models.evaluation_error import EvaluationError
from autograder.models.execution import AssessmentProvider, AssessmentRequest, ExecutionSession, ProviderAssessment
from autograder.models.frozen import thaw
from autograder.services.file_selection import select_files

EXECUTION_CAPABILITIES = frozenset({"sandbox_execution", "http_network"})


@dataclass(frozen=True)
class PreparedCriterion:
    """One criterion with its selected files and typed runtime input."""
    test: TestNode
    evaluation: EvaluationInput

    @property
    def criterion_id(self) -> str:
        return self.test.criterion_id


def prepare_criteria(criteria: CriteriaTree, submission: Submission,
                     session: ExecutionSession | None = None) -> tuple[PreparedCriterion, ...]:
    """Select files for every criterion in execution order, using one policy."""
    prepared = []
    for test in criteria.get_all_tests():
        files = select_files(test, submission.submission_files, submission.evaluation_scope, submission.language)
        prepared.append(PreparedCriterion(test, EvaluationInput(
            files=tuple(files), language=submission.language, locale=submission.locale,
            # Only evaluators declaring execution receive the session.
            session=session if test.capabilities & EXECUTION_CAPABILITIES else None,
        )))
    return tuple(prepared)


def assess_criteria(criteria: CriteriaTree, submission: Submission, *,
                    session: ExecutionSession | None = None,
                    ai: AssessmentProvider | None = None) -> dict[str, TestResult]:
    """Return one validated result per criterion ID, in execution order."""
    prepared = prepare_criteria(criteria, submission, session)
    ai_group = [item for item in prepared if isinstance(item.test.test_function, AiTestFunction)]
    # Ordinary evaluators (every process) run first, so the session's lifetime
    # covers only their deadlines; the provider call has its own deadline.
    results = {item.criterion_id: assess_one(item) for item in prepared
               if not isinstance(item.test.test_function, AiTestFunction)}
    context = {name: submission.submission_files[name].content for name in sorted(submission.submission_files)}
    if ai_group:
        results.update(assess_many(ai_group, ai, context_files=context, locale=submission.locale))
    return {item.criterion_id: results[item.criterion_id] for item in prepared}


def assess_one(item: PreparedCriterion) -> TestResult:
    """Run one ordinary evaluator with an isolated copy of its parameters."""
    result = item.test.test_function.execute(item.evaluation, **thaw(item.test.parameters))
    if not isinstance(result, TestResult) or not _valid_score(result.score) or not isinstance(result.report, str):
        raise EvaluationError("INVALID_EVALUATOR_RESULT", "An evaluator returned an invalid assessment.")
    return result


def assess_many(criteria: Sequence[PreparedCriterion], provider: AssessmentProvider | None, *,
                context_files: Mapping[str, str], locale: str) -> dict[str, TestResult]:
    """Assess a group of AI criteria with one provider call; results keyed by criterion ID.

    The provider must return exactly one valid assessment per requested ID.
    Unknown, duplicate, missing and invalid answers fail the required
    evaluation; nothing is retried, dropped or replaced by a zero.
    """
    if provider is None:
        raise EvaluationError("PROVIDER_UNAVAILABLE", "An AI assessment requires a host-supplied provider.", "provider")
    requests = []
    for item in criteria:
        prompt = item.test.test_function.build_prompt(item.evaluation, **thaw(item.test.parameters))
        if not isinstance(prompt, str) or not prompt.strip():
            raise EvaluationError("INVALID_EVALUATOR_RESULT", "An AI evaluator produced an invalid prompt.")
        requests.append(AssessmentRequest(criterion_id=item.criterion_id, prompt=prompt))
    if len({request.criterion_id for request in requests}) != len(requests):
        raise EvaluationError("INVALID_DEFINITION", "AI criterion identities must be unique.", "definition")
    if not requests:
        return {}
    try:
        answers = provider.assess(tuple(requests), context_files=dict(context_files), locale=locale)
    except EvaluationError:
        raise
    except Exception as exc:
        raise EvaluationError("PROVIDER_ERROR", "The assessment provider could not complete evaluation.",
                              "provider", True) from exc
    evaluators = {item.criterion_id: item.test.test_function.name for item in criteria}
    return _validated_assessments(answers, evaluators)


def _validated_assessments(answers, evaluators: Mapping[str, str]) -> dict[str, TestResult]:
    """Map provider answers to results, requiring exact criterion-ID coverage."""
    if isinstance(answers, (str, bytes, Mapping)) or not isinstance(answers, Sequence):
        raise EvaluationError("INVALID_EVALUATOR_RESULT", "The assessment provider returned an invalid assessment.",
                              "provider", True)
    results = {}
    for answer in answers:
        if (not isinstance(answer, ProviderAssessment) or not isinstance(answer.criterion_id, str)
                or not _valid_score(answer.score) or not isinstance(answer.report, str)):
            raise EvaluationError("INVALID_EVALUATOR_RESULT", "The assessment provider returned an invalid assessment.",
                                  "provider", True)
        if answer.criterion_id not in evaluators:
            raise EvaluationError("INVALID_EVALUATOR_RESULT", "The assessment provider returned an unknown assessment.",
                                  "provider", True)
        if answer.criterion_id in results:
            raise EvaluationError("INVALID_EVALUATOR_RESULT", "The assessment provider returned duplicate assessments.",
                                  "provider", True)
        results[answer.criterion_id] = TestResult(evaluators[answer.criterion_id], float(answer.score), answer.report)
    if results.keys() != evaluators.keys():
        raise EvaluationError("MISSING_EVALUATOR_RESULT", "A required AI assessment was not returned.", "provider", True)
    return results


def _valid_score(score) -> bool:
    return (not isinstance(score, bool) and isinstance(score, (int, float))
            and math.isfinite(score) and 0 <= score <= 100)
