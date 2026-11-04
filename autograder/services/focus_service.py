"""Order assessed criteria by their impact on the final score."""
from autograder.models.contracts.outcome import ResultOutcomeTree
from autograder.models.contracts.scoring import iter_test_shares
from autograder.models.dataclass.focus import Focus, FocusedTest


def find_focus(tree: ResultOutcomeTree) -> Focus:
    """Rank each category's tests by points missed on the 0-100 root scale.

    Impact is ``(100 - score) * share`` with the effective share from the
    shared scoring traversal; ties keep the canonical criterion order.
    """
    ranked = {"base": [], "bonus": None, "penalty": None}
    for category, test, share in iter_test_shares(tree):
        if ranked[category] is None:
            ranked[category] = []
        ranked[category].append(FocusedTest(test_result=test, diff_score=(100 - test.score) * share))
    for tests in ranked.values():
        if tests:
            tests.sort(key=lambda focused: focused.diff_score, reverse=True)
    return Focus(base=tuple(ranked["base"]), bonus=_frozen(ranked["bonus"]), penalty=_frozen(ranked["penalty"]))


def _frozen(tests):
    return tuple(tests) if tests is not None else None
