"""Definition-versus-outcome structural verification, shared by every producer.

A completed outcome must place exactly the compiled criteria: same categories,
holder names and order, criterion IDs, evaluator types, labels and file targets,
with effective weights equal to the definition's ratios. Reported parameters are
optional on the v1 wire; when present they must equal the canonical parameters.
Locally produced trees and externally attested trees pass the same check.
Arithmetic invariants (holder and final scores) are validated independently by
the outcome models themselves.

The definition also fixes the worst-case serialized size of any of its outcomes
(``CompiledDefinition.max_outcome_bytes``, measured by ``grading``); compilation
keeps definition plus outcome within ``MAX_ATTESTATION_BYTES`` and attestations
above the bound are rejected.
"""
from math import isclose

from autograder.models.contracts.outcome import CompletedOutcome, FailedOutcome, ResultOutcomeTree, wire_bytes
from autograder.models.contracts.scoring import CATEGORIES, child_weights
from autograder.models.criteria_tree import CriteriaTree
from autograder.models.frozen import thaw

WEIGHT_TOLERANCE = 0.00001

#: Definition snapshot plus worst-case outcome: what every attestation carries.
#: Hosts accept requests of at least this size plus their own envelope.
MAX_ATTESTATION_BYTES = 24 * 1024 * 1024


class OutcomeTooLargeError(ValueError):
    """An outcome exceeds the worst-case size its definition allows."""

    def __init__(self, size: int, limit: int):
        super().__init__(f"Outcome serializes to {size} bytes; its definition allows at most {limit}")


class OutcomeStructureError(ValueError):
    """The result tree does not match its definition's structure or weights."""

    def __init__(self, message="Result tree structure, identities or scoring weights do not match its definition snapshot"):
        super().__init__(message)


def verify_outcome_tree(criteria: CriteriaTree, tree: ResultOutcomeTree) -> None:
    """Raise ``OutcomeStructureError`` unless ``tree`` places exactly ``criteria``."""
    for name in CATEGORIES:
        expected, actual = getattr(criteria, name), getattr(tree, name)
        if (expected is None) != (actual is None):
            raise OutcomeStructureError()
        if expected is not None:
            if not isclose(expected.weight, actual.weight, abs_tol=WEIGHT_TOLERANCE):
                raise OutcomeStructureError()
            _verify_holder(expected, actual)


def _verify_holder(expected, actual) -> None:
    if actual.name != expected.name or len(actual.subjects) != len(expected.subjects) \
            or len(actual.tests) != len(expected.tests):
        raise OutcomeStructureError()
    subject_weights, test_weights = child_weights(expected)
    for subject, result, weight in zip(expected.subjects, actual.subjects, subject_weights):
        if not isclose(result.weight, weight, abs_tol=WEIGHT_TOLERANCE):
            raise OutcomeStructureError()
        _verify_holder(subject, result)
    for test, result, weight in zip(expected.tests, actual.tests, test_weights):
        target = tuple(test.file_target) if test.file_target is not None else None
        if (not isclose(result.weight, weight, abs_tol=WEIGHT_TOLERANCE)
                or result.id != test.criterion_id or result.evaluator != test.test_function.name
                or result.name != test.name or result.file_target != target
                # Parameters are optional on the v1 wire; reported ones must be canonical.
                or (result.parameters and thaw(result.parameters) != thaw(test.parameters))):
            raise OutcomeStructureError()


def verify_outcome_size(limit: int, outcome: CompletedOutcome | FailedOutcome) -> None:
    """Raise ``OutcomeTooLargeError`` when an (attested) outcome exceeds ``limit``.

    Locally produced outcomes are within the limit by construction; attested ones
    are rejected, never truncated.
    """
    size = wire_bytes(outcome.model_dump(mode="json"))
    if size > limit:
        raise OutcomeTooLargeError(size, limit)
