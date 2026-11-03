"""Pure comparison of two assessed trees, joined by criterion ID.

Baseline selection, compatibility and retry policy belong to the host (#375);
this utility only derives deltas from two authoritative result trees.
"""
from autograder.models.contracts.outcome import ComparisonContent, CriterionDelta, ResultOutcomeTree, score_vector


def compare(baseline: ResultOutcomeTree, head: ResultOutcomeTree) -> ComparisonContent:
    """Head criteria in canonical order, then criteria removed since the baseline."""
    before, after = score_vector(baseline), score_vector(head)
    deltas = []
    for criterion_id in [*after, *(identity for identity in before if identity not in after)]:
        if criterion_id not in before:
            deltas.append(CriterionDelta(path=criterion_id, status="introduced", head_score=after[criterion_id]))
        elif criterion_id not in after:
            deltas.append(CriterionDelta(path=criterion_id, status="removed", baseline_score=before[criterion_id]))
        else:
            delta = round(after[criterion_id] - before[criterion_id], 2)
            status = "improved" if delta > 0 else "regressed" if delta < 0 else "unchanged"
            deltas.append(CriterionDelta(path=criterion_id, status=status, baseline_score=before[criterion_id],
                                         head_score=after[criterion_id], delta=delta))
    score_delta = round(head.score - baseline.score, 2)
    return ComparisonContent(score_delta=score_delta, improved=score_delta > 0, test_deltas=tuple(deltas))
