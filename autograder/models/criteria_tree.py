from typing import List, Any
from autograder.models.dataclass.test_result import TestResult
from autograder.utils.formatters.criteria_tree import PreExecutedTreeFormatter
from autograder.utils.printers.criteria_tree import CriteriaTreePrinter


class TestCall:
    """Represents a single invocation of a test function with its arguments."""

    def __init__(self, args: List[Any]):
        self.args = args

    def __repr__(self):
        return f"TestCall(args={self.args})"


class Test:
    """
    Represents a group of calls to a single test function in the library.
    This is a LEAF node in the grading tree.
    """

    def __init__(self, name: str, filename: str | None = None):
        self.name: str = name
        self.file: str | None = filename
        self.calls: List[TestCall] = []

    def add_call(self, call: TestCall):
        self.calls.append(call)

    def get_result(
        self, test_library, submission_files, subject_name: str
    ) -> List[TestResult]:
        """
        Retrieves a TestFunction object from the library and executes it for each TestCall.
        """
        try:
            # Get the TestFunction instance (e.g., HasTag()) from the library
            test_function_instance = test_library.get_test(self.name)
        except AttributeError as e:
            return [TestResult(self.name, 0, f"ERROR: {e}", subject_name)]

        file_content_to_pass = None
        if self.file:
            # --- File Injection Logic ---
            if self.file == "all":
                file_content_to_pass = submission_files
            else:
                file_content_to_pass = submission_files.get(self.file)
                if file_content_to_pass is None:
                    return [
                        TestResult(
                            self.name,
                            0,
                            f"Erro: O arquivo necessário '{self.file}' não foi encontrado na submissão.",
                            subject_name,
                        )
                    ]

        # --- Execution Logic ---
        if not self.calls:
            # Execute with just the file content if no specific calls are defined
            if file_content_to_pass:
                result = test_function_instance.execute(file_content_to_pass)
            else:
                result = test_function_instance.execute()
            result.subject_name = subject_name
            return [result]

        results = []
        for call in self.calls:
            # Execute the 'execute' method of the TestFunction instance
            if file_content_to_pass:
                result = test_function_instance.execute(
                    file_content_to_pass, *call.args
                )
            else:
                result = test_function_instance.execute(*call.args)
            result.subject_name = subject_name
            results.append(result)
        return results

    def __repr__(self):
        return f"Test(name='{self.name}', file='{self.file}', calls={len(self.calls)})"


class Subject:
    """
    Represents a subject, which can contain a list of tests AND/OR
    a list of nested subjects. This is a BRANCH and/or LEAF-HOLDER node.
    """

    def __init__(self, name, weight=0):
        self.name = name
        self.weight = weight
        self.tests: List[Test] = list()
        self.subjects: List[Subject] = list()

    def __repr__(self):
        return f"Subject(name={self.name}, weight={self.weight}, subjects={len(self.subjects)}, tests={len(self.tests)})"


class TestCategory:
    """
    Represents one of the three main categories: base, bonus, or penalty.
    Can contain a list of tests AND/OR a list of subjects.
    """

    def __init__(self, name, max_score=100):
        self.name = name
        self.max_score = max_score
        self.subjects: List[Subject] = list()
        self.tests: List[Test] = list()

    def set_weight(self, weight):
        self.max_score = weight

    def add_subject(self, subject: Subject):
        self.subjects.append(subject)

    def add_subjects(self, subjects: List[Subject]) -> None:
        self.subjects.extend(subjects)

    def __repr__(self):
        return f"TestCategory(name='{self.name}', max_score={self.max_score}, subjects={len(self.subjects)}, tests={len(self.tests)})"


class CriteriaTree:
    """The ROOT of the criteria tree."""

    def __init__(self, bonus_weight=0, penalty_weight=0):
        self.base = TestCategory("base")
        self.bonus = TestCategory("bonus", max_score=bonus_weight)
        self.penalty = TestCategory("penalty", max_score=penalty_weight)

    def __repr__(self):
        return "Criteria(categories=['base', 'bonus', 'penalty'])"

    def print_tree(self):
        """Prints a visual representation of the entire criteria tree."""
        printer = CriteriaTreePrinter()
        printer.print_tree(self)

    def print_pre_executed_tree(self):
        """Prints a visual representation of the entire pre-executed criteria tree."""
        printer = CriteriaTreePrinter(PreExecutedTreeFormatter())
        printer.print_tree(self)
