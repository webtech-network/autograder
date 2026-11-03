"""Criterion identity survives display labels, grouping and serialization.

Score vectors are only derived from the canonical outcome tree; the internal
result tree converts to that tree exactly as the engine does at finalization.
"""
import pytest
from pydantic import ValidationError

from autograder.models.contracts.outcome import ResultOutcomeTree, iter_outcome_tests
from autograder.models.result_tree import CategoryResultNode, ResultTree, RootResultNode, SubjectResultNode, TestResultNode


def tree(*tests):
    value = ResultTree(RootResultNode(base=CategoryResultNode("base", 100, tests=list(tests))))
    value.calculate_final_score()
    return value


def leaf(identity, score=100, name="Repeated label"):
    return TestResultNode(name=name, criterion_id=identity, evaluator="check", score=score, report="")


def vector(value):
    canonical = ResultOutcomeTree.model_validate(value.root.to_dict())
    return {test.id: test.score for test in iter_outcome_tests(canonical)}


def test_duplicate_labels_have_independent_ids():
    assert vector(tree(leaf("one", 100), leaf("two", 0))) == {"one": 100, "two": 0}


def test_round_trip_preserves_identity_without_duplicate_tree():
    value = tree(leaf("one", 50))
    serialized = value.to_dict()
    assert "tree" in serialized and "root" not in serialized
    assert vector(ResultTree.from_dict(serialized)) == {"one": 50}


@pytest.mark.parametrize("identity", [None, "same"])
def test_missing_and_duplicate_ids_are_not_silently_overwritten(identity):
    with pytest.raises((ValidationError, ValueError)):
        vector(tree(leaf(identity), leaf(identity)))


def test_nested_grouping_does_not_change_identity():
    node = leaf("stable", 75, name="Renamed")
    value = ResultTree(RootResultNode(base=CategoryResultNode("base", 100,
        subjects=[SubjectResultNode("Renamed group", subjects=[SubjectResultNode("Inner", tests=[node])])])))
    value.calculate_final_score()
    assert vector(value) == {"stable": 75}
