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
    Represents a group of calls to a single test function in the library.
    This is a LEAF node in the grading tree.
    """
    def __init__(self, name: str):
        self.name = name
        self.calls: List[TestCall] = []

    def add_call(self, call: TestCall):
        self.calls.append(call)

    def execute(self, test_library, submission_files) -> List['TestResult']:
        """
        Finds and executes a function from the test library for each TestCall
        and returns a list of all the resulting TestResult objects.
        """
        try:
            test_function = getattr(test_library, self.name)
        except AttributeError:
            # If the function is missing, return a single failed result
            return [TestResult(self.name, 0, f"ERROR: Test function '{self.name}' not found in library.")]

        # If there are no specific calls, run the function once with no arguments
        if not self.calls:
            return [test_function(submission_files)]

        # --- Execute each call and collect all TestResult objects ---
        return [
            test_function(submission_files, *call.args) for call in self.calls
        ]

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
    def __init__(self):
        self.base = TestCategory("base")
        self.bonus = TestCategory("bonus")
        self.penalty = TestCategory("penalty")

    def __repr__(self):
        return f"Criteria(categories=['base', 'bonus', 'penalty'])"

    def print_tree(self):
        """Prints a visual representation of the entire criteria tree."""
        print(f"🌲 Criteria Tree")
        self._print_category(self.base, prefix="  ")
        self._print_category(self.bonus, prefix="  ")
        self._print_category(self.penalty, prefix="  ")

    def _print_category(self, category: TestCategory, prefix: str):
        """Helper method to print a category and its subjects."""
        if not category.subjects:
            return
        print(f"{prefix}📁 {category.name.upper()}")
        for subject in category.subjects.values():
            self._print_subject(subject, prefix=prefix + "    ")

    def _print_subject(self, subject: Subject, prefix: str):
        """Recursive helper method to print a subject and its contents."""
        print(f"{prefix}📘 {subject.name} (weight: {subject.weight})")

        # If the subject has sub-subjects, recurse
        if subject.subjects is not None:
            for sub in subject.subjects.values():
                self._print_subject(sub, prefix=prefix + "    ")

        # If the subject has tests, print them
        if subject.tests is not None:
            for test in subject.tests:
                print(f"{prefix}  - 🧪 {test.name}")
                for call in test.calls:
                    print(f"{prefix}    - Parameters: {call.args}")



