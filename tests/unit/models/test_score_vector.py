"""Criterion identity survives display labels, grouping and serialization."""
import pytest
from autograder.models.result_tree import CategoryResultNode, ResultTree, RootResultNode, SubjectResultNode, TestResultNode


def tree(*tests):
    value = ResultTree(RootResultNode(base=CategoryResultNode("base", 100, tests=list(tests))))
    value.calculate_final_score()
    return value


def leaf(identity, score=100, name="Repeated label"):
    return TestResultNode(name=name, criterion_id=identity, evaluator="check", score=score, report="")


def test_duplicate_labels_have_independent_ids():
    value = tree(leaf("one", 100), leaf("two", 0))
    assert value.to_score_vector() == {"one": 100, "two": 0}
    assert list(value.iter_test_results())[0][0] == "one"


def test_round_trip_preserves_identity_without_duplicate_tree():
    value = tree(leaf("one", 50))
    serialized = value.to_dict()
    assert "tree" in serialized and "root" not in serialized
    assert ResultTree.from_dict(serialized).to_score_vector() == {"one": 50}


@pytest.mark.parametrize("identity", [None, "same"])
def test_missing_and_duplicate_ids_are_not_silently_overwritten(identity):
    with pytest.raises(ValueError):
        tree(leaf(identity), leaf(identity)).to_score_vector()


def test_nested_grouping_does_not_change_identity():
    node = leaf("stable", 75, name="Renamed")
    value = ResultTree(RootResultNode(base=CategoryResultNode("base", 100,
        subjects=[SubjectResultNode("Renamed group", subjects=[SubjectResultNode("Inner", tests=[node])])])))
    value.calculate_final_score()
    assert value.to_score_vector() == {"stable": 75}
