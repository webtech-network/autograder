from typing import List, Any

from autograder.core.models.test_result import TestResult


# ===============================================================
# 1. Classes for Test Execution
# ===============================================================

class TestCall:
    """Represents a single invocation of a test function with its arguments."""
    def __init__(self, args: List[Any]):
        self.args = args

    def __repr__(self):
        return f"TestCall(args={self.args})"

# ===============================================================
# 2. Classes for the Tree Structure
# ===============================================================

class Test:
    """
    Represents a test to be executed by looking up its name in a test library
    and running it for each TestCall. This is a LEAF node in the tree.
    """
    def __init__(self, name: str):
        self.name = name
        self.calls: List[TestCall] = []

    def add_call(self, call: TestCall):
        self.calls.append(call)

    def execute(self, test_library, submission_files) -> TestResult:
        """
        Finds the test function in the library and executes it for each call.
        For simplicity, this example averages the scores of all calls.
        """
        try:
            test_function = getattr(test_library, self.name)
        except AttributeError:
            return TestResult(self.name, 0, f"ERROR: Test function '{self.name}' not found in library.")

        call_scores = []
        call_reports = []

        for call in self.calls:
            result = test_function(submission_files, *call.args)
            call_scores.append(result.score)
            call_reports.append(result.report)

        # Average the scores from all calls for this test
        final_score = sum(call_scores) / len(call_scores) if call_scores else 100
        final_report = " | ".join(call_reports)

        return TestResult(self.name, int(final_score), final_report)

    def __repr__(self):
        return f"Test(name='{self.name}', calls={len(self.calls)})"


class Subject:
    """
    Represents a subject, which can contain EITHER a list of tests OR
    a dictionary of nested subjects. This is a BRANCH or LEAF-HOLDER node.
    """
    def __init__(self, name, weight=0):
        self.name = name
        self.weight = weight
        self.tests: List[Test] | None = None
        self.subjects: dict[str, 'Subject'] | None = None

    def __repr__(self):
        if self.subjects is not None:
            return f"Subject(name='{self.name}', weight={self.weight}, subjects={len(self.subjects)})"
        return f"Subject(name='{self.name}', weight={self.weight}, tests={len(self.tests)})"


class TestCategory:
    """Represents one of the three main categories: base, bonus, or penalty."""
    def __init__(self, name):
        self.name = name
        self.subjects: dict[str, Subject] = {}

    def add_subject(self, subject: Subject):
        self.subjects[subject.name] = subject

    def __repr__(self):
        return f"TestCategory(name='{self.name}', subjects={list(self.subjects.keys())})"


class Criteria:
    """The ROOT of the criteria tree."""
    def __init__(self, test_library_name: str):
        self.base = TestCategory("base")
        self.bonus = TestCategory("bonus")
        self.penalty = TestCategory("penalty")

    def __repr__(self):
        return f"Criteria(categories=['base', 'bonus', 'penalty'])"



