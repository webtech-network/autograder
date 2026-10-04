"""Comparison joins criterion IDs, never display paths."""
import pytest
from autograder.services.result_comparator import ResultComparator
from tests.unit.models.test_score_vector import tree, leaf


@pytest.mark.parametrize("before,after,status", [(50,75,"improved"),(75,50,"regressed"),(75,75,"unchanged")])
def test_comparison_scores(before, after, status):
    comparison = ResultComparator.compare(tree(leaf("id", before)), tree(leaf("id", after)))
    assert comparison.score_delta == after - before
    assert comparison.improved is (after > before)
    assert comparison.test_deltas[0].path == "id"
    assert comparison.test_deltas[0].status == status
    assert comparison.test_deltas[0].delta == after - before


def test_rename_and_duplicate_display_labels_do_not_reidentify_tests():
    result = ResultComparator.compare(tree(leaf("a", 0, "Old"), leaf("b", 100, "Old")),
                                      tree(leaf("a", 100, "New"), leaf("b", 100, "New")))
    assert [delta.path for delta in result.test_deltas] == ["a", "b"]
    assert [delta.status for delta in result.test_deltas] == ["improved", "unchanged"]


def test_added_and_removed_criteria_are_explicit():
    result = ResultComparator.compare(tree(leaf("removed")), tree(leaf("new")))
    assert [(delta.path, delta.status) for delta in result.test_deltas] == [("new","introduced"),("removed","removed")]
    assert all(delta.delta is None for delta in result.test_deltas)
    assert result.to_dict()["test_deltas"][0]["path"] == "new"
