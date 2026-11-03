"""Comparison joins criterion IDs from authoritative trees, never display paths."""
import pytest
from autograder.models.contracts.outcome import ComparisonContent
from autograder.services.result_comparator import compare
from tests.grading import leaf, outcome_tree as tree


@pytest.mark.parametrize("before,after,status", [(50,75,"improved"),(75,50,"regressed"),(75,75,"unchanged")])
def test_comparison_scores(before, after, status):
    comparison = compare(tree(leaf("id", before)), tree(leaf("id", after)))
    assert isinstance(comparison, ComparisonContent)
    assert comparison.score_delta == after - before
    assert comparison.improved is (after > before)
    assert comparison.test_deltas[0].path == "id"
    assert comparison.test_deltas[0].status == status
    assert comparison.test_deltas[0].delta == after - before


def test_rename_and_duplicate_display_labels_do_not_reidentify_tests():
    result = compare(tree(leaf("a", 0, "Old / x"), leaf("b", 100, "Old / x")),
                     tree(leaf("a", 100, "New / x"), leaf("b", 100, "New / x")))
    assert [delta.path for delta in result.test_deltas] == ["a", "b"]
    assert [delta.status for delta in result.test_deltas] == ["improved", "unchanged"]


def test_added_and_removed_criteria_are_explicit():
    result = compare(tree(leaf("removed")), tree(leaf("new")))
    assert [(delta.path, delta.status) for delta in result.test_deltas] == [("new","introduced"),("removed","removed")]
    assert all(delta.delta is None for delta in result.test_deltas)
    assert result.model_dump(mode="json")["test_deltas"][0]["path"] == "new"


def test_bonus_and_penalty_criteria_are_compared_by_id():
    baseline = tree(leaf("base", 100), bonus=(10, [leaf("extra", 0)]), penalty=(20, [leaf("style", 0)]))
    head = tree(leaf("base", 100), bonus=(10, [leaf("extra", 100)]), penalty=(20, [leaf("style", 100)]))
    result = compare(baseline, head)
    assert (baseline.score, head.score, result.score_delta) == (80, 100, 20)
    assert [(d.path, d.status) for d in result.test_deltas] == [
        ("base", "unchanged"), ("extra", "improved"), ("style", "improved")]
