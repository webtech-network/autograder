"""Test helpers: assess a criteria tree and aggregate its results like the pipeline."""
from autograder.models.criteria_tree import CategoryNode, CriteriaTree
from autograder.models.dataclass.submission import Submission
from autograder.models.execution import ProviderAssessment
from autograder.services.assessment import assess_criteria
from autograder.services.grader.grader_service import GraderService


def grade(criteria, files=None, *, session=None, ai=None, language=None, locale="en", scope=None):
    """Assess every criterion (one AI batch) and return the weighted result tree."""
    if isinstance(criteria, CategoryNode):
        criteria = CriteriaTree(base=criteria)
    submission = Submission("student", "opaque", "opaque", dict(files or {}), language=language,
                            locale=locale, evaluation_scope=scope)
    results = assess_criteria(criteria, submission, session=session, ai=ai)
    return GraderService().grade_from_tree(criteria, results)


class FakeProvider:
    """Records each batch call; answers every request unless told otherwise.

    ``answer(requests)`` may return any provider output, including invalid ones.
    """

    def __init__(self, answer=None, score=100.0):
        self.calls = []
        self.answer = answer or (lambda requests: [
            ProviderAssessment(request.criterion_id, score, f"assessed {request.criterion_id}")
            for request in requests])

    def assess(self, requests, *, context_files, locale):
        self.calls.append((tuple(requests), dict(context_files), locale))
        return self.answer(requests)
