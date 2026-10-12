"""The grading contract's relative sibling weights, shared with host attestation."""
import math
from typing import Sequence


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
