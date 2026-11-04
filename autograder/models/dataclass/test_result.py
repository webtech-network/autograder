from dataclasses import dataclass


@dataclass(frozen=True)
class TestResult:
    """An evaluator's assessment of one criterion: a 0-100 score and a report.

    ``test_name`` is informational (conventionally the evaluator name). The
    result tree takes the criterion ID, evaluator ID, label, file target and
    canonical parameters from the compiled criterion, never from this value.
    """

    test_name: str
    score: float
    report: str = ""
