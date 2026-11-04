"""Criterion identity survives display labels, grouping and serialization."""
import pytest
from pydantic import ValidationError

from autograder.models.contracts.outcome import ResultOutcomeTree, score_vector
from autograder.models.contracts.scoring import iter_tests
from tests.grading import leaf, outcome_tree as tree


def test_duplicate_labels_and_slashes_have_independent_ids():
    value = tree(leaf("one", 100, "Group / check"), leaf("two", 0, "Group / check"))
    assert score_vector(value) == {"one": 100, "two": 0}
    assert [test.id for _, test in iter_tests(value)] == ["one", "two"]


def test_round_trip_preserves_every_result_field():
    value = tree(leaf("one", 50, file_target=["index.html"], parameters={"tag": "main", "nested": [1, {"a": None}]},
                      report="half", metadata={"note": "kept"}))
    serialized = value.model_dump(mode="json")
    restored = ResultOutcomeTree.model_validate(serialized)
    assert restored == value and restored.model_dump(mode="json") == serialized
    [test] = restored.base.tests
    assert test.file_target == ("index.html",)
    assert test.parameters == {"tag": "main", "nested": [1, {"a": None}]}
    assert score_vector(restored) == {"one": 50}


def test_duplicate_ids_are_rejected_rather_than_overwritten():
    with pytest.raises(ValidationError, match="Criterion IDs must be unique"):
        tree(leaf("same"), leaf("same"))


def test_nested_grouping_does_not_change_identity():
    node = leaf("stable", 75, name="Renamed", weight=100)
    value = ResultOutcomeTree.model_validate({"score": 75, "base": {"name": "base", "weight": 100, "score": 75,
        "subjects": [{"name": "Renamed group", "weight": 100, "score": 75, "subjects": [
            {"name": "Inner", "weight": 100, "score": 75, "tests": [node]}]}]}})
    assert score_vector(value) == {"stable": 75}
