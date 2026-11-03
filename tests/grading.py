"""Test helpers: assess a criteria tree and build its result tree like the pipeline."""
from autograder.models.criteria_tree import CategoryNode, CriteriaTree
from autograder.models.dataclass.submission import Submission
from autograder.models.execution import ProviderAssessment
from autograder.services.assessment import assess_criteria
from autograder.services.grading import grade as build_tree


def grade(criteria, files=None, *, session=None, ai=None, language=None, locale="en", scope=None):
    """Assess every criterion (one AI batch) and return the canonical ``ResultOutcomeTree``."""
    if isinstance(criteria, CategoryNode):
        criteria = CriteriaTree(base=criteria)
    submission = Submission("student", "opaque", "opaque", dict(files or {}), language=language,
                            locale=locale, evaluation_scope=scope)
    results = assess_criteria(criteria, submission, session=session, ai=ai)
    return build_tree(criteria, results)


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


def leaf(identity, score=100, name="Repeated label", **extra):
    """One assessed criterion as canonical outcome data."""
    return {"id": identity, "evaluator": "check", "name": name, "score": score, "report": "", **extra}


def outcome_tree(*tests, **categories):
    """A valid ``ResultOutcomeTree`` with equally weighted base tests.

    ``categories`` may add ``bonus``/``penalty`` as ``(cap, [leaf, ...])``.
    """
    from autograder.models.contracts.outcome import ResultOutcomeTree  # pylint: disable=import-outside-toplevel
    from autograder.models.contracts.scoring import final_score, holder_score  # pylint: disable=import-outside-toplevel

    def category(name, cap, leaves):
        weighted = [{**test, "weight": test.get("weight", 100 / len(leaves))} for test in leaves]
        score = holder_score([(test["score"], test["weight"]) for test in weighted])
        return {"name": name, "weight": cap, "score": round(score, 2), "tests": weighted}

    data = {"base": category("base", 100, list(tests))}
    for name, (cap, leaves) in categories.items():
        data[name] = category(name, cap, leaves)
    data["score"] = round(final_score(data["base"]["score"],
                                      *[(data[name]["score"], data[name]["weight"]) if name in data else None
                                        for name in ("bonus", "penalty")]), 2)
    return ResultOutcomeTree.model_validate(data)
