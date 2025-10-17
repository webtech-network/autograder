"""Test Result module."""


class TestResult:
    """Stores the outcome of a single test execution from the test library."""

    def __init__(
        self,
        test_name: str,
        score: int,
        report: str,
        subject_name: str = "",
        parameters: dict = None,
    ):
        self.test_name = test_name
        self.score = score
        self.report = report
        self.subject_name = subject_name  # Added reference to the subject
        self.parameters = parameters if parameters is not None else {}

    def get_result(self, *args, **kwargs):
        return [self]

    def to_dict(self):
        return {
            "test_name": self.test_name,
            "score": self.score,
            "report": self.report,
            "subject_name": self.subject_name,
            "parameters": self.parameters,
        }

    def __repr__(self):
        return f"TestResult(subject='{self.subject_name}', name='{self.test_name}', score={self.score})"
