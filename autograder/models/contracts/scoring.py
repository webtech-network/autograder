"""The one definition of criterion traversal, effective weights and score arithmetic.

Grading (``autograder.services.grading``), outcome validation
(``outcome.py``), definition-versus-outcome verification
(``verification.py``), focus selection and comparison all use these functions.
They depend only on the shape shared by compiled criteria and assessed trees:
``base``/``bonus``/``penalty`` categories whose holders have ``subjects`` and
``tests``.

Arithmetic contract (documented in OUTCOMES.md):

* Sibling weights are ratios; all-zero siblings share equally. A holder with
  both subjects and tests splits 100 by ``subjects_weight``.
* A holder's score is the weighted mean of its children's unrounded scores.
* Final score = base + bonus/100*cap - (100-penalty)/100*cap, clamped to 0-100.
* Reported scores are rounded to two decimals; weights are not rounded.
"""
import math
from typing import Iterator, Optional, Sequence, Tuple

CATEGORIES = ("base", "bonus", "penalty")


def normalized_sibling_weights(weights: Sequence[float], factor: float = 1.0) -> list[float]:
    """Allocate 100 * factor by ratio; all-zero siblings share equally.

    Scaling by the maximum keeps finite large weights from overflowing their sum.
    Definition validation owns finite nonnegative input checks.
    """
    if not weights:
        return []
    target = 100.0 * factor
    maximum = max(weights)
    if maximum == 0:
        return [target / len(weights)] * len(weights)
    total = math.fsum(weight / maximum for weight in weights)
    return [target * (weight / maximum) / total for weight in weights]


def child_weights(holder) -> Tuple[list[float], list[float]]:
    """Effective weights of a compiled holder's subjects and tests (summing to 100)."""
    subjects_factor = tests_factor = 1.0
    if holder.subjects and holder.tests:
        if holder.subjects_weight is None:
            raise ValueError(f"missing 'subjects_weight' for {holder.name}")
        subjects_factor = holder.subjects_weight / 100.0
        tests_factor = 1 - subjects_factor
    return (normalized_sibling_weights([subject.weight for subject in holder.subjects], subjects_factor),
            normalized_sibling_weights([test.weight for test in holder.tests], tests_factor))


def holder_score(children: Sequence[Tuple[float, float]]) -> float:
    """Weighted mean of ``(score, weight)`` children; 0 without positive weight."""
    total_weight = sum(weight for _, weight in children)
    if not children or total_weight == 0:
        return 0.0
    return sum(score * weight for score, weight in children) / total_weight


def final_score(base: float, bonus: Optional[Tuple[float, float]] = None,
                penalty: Optional[Tuple[float, float]] = None) -> float:
    """Combine category scores; ``bonus``/``penalty`` are ``(score, cap)`` pairs."""
    bonus_points = bonus[0] / 100.0 * bonus[1] if bonus else 0.0
    penalty_points = (100.0 - penalty[0]) / 100.0 * penalty[1] if penalty else 0.0
    return max(0.0, min(100.0, base + bonus_points - penalty_points))


def report_score(score: float) -> float:
    """The documented rounding of every reported score."""
    return round(score, 2)


def categories(tree) -> Iterator[Tuple[str, object]]:
    """Present categories as ``(name, holder)`` in base, bonus, penalty order."""
    for name in CATEGORIES:
        holder = getattr(tree, name)
        if holder is not None:
            yield name, holder


def iter_holder_tests(holder) -> Iterator[object]:
    """Tests under a holder: nested subjects first, then direct tests."""
    for subject in holder.subjects:
        yield from iter_holder_tests(subject)
    yield from holder.tests


def iter_tests(tree) -> Iterator[Tuple[str, object]]:
    """Every ``(category, test)`` in the canonical criterion order."""
    for name, holder in categories(tree):
        for test in iter_holder_tests(holder):
            yield name, test


def iter_test_shares(tree) -> Iterator[Tuple[str, object, float]]:
    """For an assessed tree, yield ``(category, test, share)``.

    ``share`` is the fraction of the category's points this test controls:
    the product of its own and every ancestor's effective weight / 100, times
    the category weight / 100 (base 100, bonus/penalty caps). A test's impact on
    the final score is ``(100 - score) * share``.
    """
    def walk(holder, multiplier):
        for subject in holder.subjects:
            yield from walk(subject, multiplier * subject.weight / 100.0)
        for test in holder.tests:
            yield test, multiplier * test.weight / 100.0

    for name, holder in categories(tree):
        for test, share in walk(holder, holder.weight / 100.0):
            yield name, test, share
