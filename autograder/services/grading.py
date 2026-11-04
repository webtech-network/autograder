"""Aggregate ID-keyed assessed results into the canonical result tree, once.

The assessed tree is the terminal ``ResultOutcomeTree``: every leaf owns its
criterion ID, evaluator ID, label, file target, canonical parameters, score and
report as data, with no reference to compiled nodes or evaluator instances.
Focus, feedback, score vectors and comparison derive from this tree.

This is the one place where locally produced reports are bounded: whatever an
evaluator (or AI provider) returns, the tree keeps a deterministic excerpt of at
most ``MAX_REPORT_BYTES``. The score is never affected.
"""
from typing import Mapping

from pydantic import ValidationError

from autograder.models.contracts.outcome import MAX_REPORT_BYTES, ResultOutcomeTree, bound_text
from autograder.models.contracts.scoring import (
    categories, child_weights, final_score, holder_score, report_score,
)
from autograder.models.criteria_tree import CriteriaTree
from autograder.models.dataclass.test_result import TestResult
from autograder.models.evaluation_error import EvaluationError
from autograder.models.frozen import thaw


def grade(criteria: CriteriaTree, results: Mapping[str, TestResult]) -> ResultOutcomeTree:
    """Place every criterion's result with its effective weight and score the tree.

    Executes no evaluator. A missing result or a tree that violates the outcome
    invariants is a required failure.
    """
    def test_node(test, weight):
        if test.criterion_id not in results:
            raise EvaluationError("MISSING_EVALUATOR_RESULT", "A required assessment was not produced.")
        result = results[test.criterion_id]
        return result.score, {
            "id": test.criterion_id, "evaluator": test.test_function.name, "type": "test", "name": test.name,
            "score": report_score(result.score), "weight": weight,
            "report": bound_text(result.report, MAX_REPORT_BYTES),
            "file_target": list(test.file_target) if test.file_target is not None else None,
            "parameters": thaw(test.parameters), "metadata": {},
        }

    def holder_node(holder, kind, weight):
        subject_weights, test_weights = child_weights(holder)
        subjects = [holder_node(subject, "subject", share) for subject, share in zip(holder.subjects, subject_weights)]
        tests = [test_node(test, share) for test, share in zip(holder.tests, test_weights)]
        score = holder_score([(raw, data["weight"]) for raw, data in (*subjects, *tests)])
        return score, {
            "name": holder.name, "type": kind, "weight": weight, "score": report_score(score),
            "subjects": [data for _, data in subjects], "tests": [data for _, data in tests], "metadata": {},
        }

    scored = {name: holder_node(holder, "category", holder.weight) for name, holder in categories(criteria)}
    score = final_score(
        scored["base"][0],
        (scored["bonus"][0], criteria.bonus.weight) if "bonus" in scored else None,
        (scored["penalty"][0], criteria.penalty.weight) if "penalty" in scored else None,
    )
    data = {"name": "root", "type": "root", "score": report_score(score), "metadata": {},
            **{name: node for name, (_, node) in scored.items()}}
    try:
        return ResultOutcomeTree.model_validate(data)
    except (ValidationError, TypeError, ValueError) as exc:
        raise EvaluationError("INVALID_EVALUATOR_RESULT", "The grading execution produced an invalid assessment.",
                              "internal") from exc
