from typing import List, Any
from autograder.context import request_context
from autograder.core.models.test_result import TestResult


# Assuming TestResult is defined in a separate, importable file
# from autograder.core.models.test_result import TestResult

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
    def __init__(self, name: str, filename: str = None):
        self.name = name
        self.file = filename  # The file this test operates on (e.g., "index.html")
        self.calls: List[TestCall] = []

    def add_call(self, call: TestCall):
        self.calls.append(call)

    def get_result(self, test_library, submission_files, subject_name: str) -> List[TestResult]:
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
                    return [TestResult(self.name, 0, f"Erro: O arquivo necessário '{self.file}' não foi encontrado na submissão.", subject_name)]

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
                result = test_function_instance.execute(file_content_to_pass, *call.args)
            else:
                result = test_function_instance.execute(*call.args)
            result.subject_name = subject_name
            results.append(result)
        return results

    def __repr__(self):
        return f"Test(name='{self.name}', file='{self.file}', calls={len(self.calls)})"

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
        return f"Subject(name='{self.name}', weight={self.weight}, tests={self.tests})"


class TestCategory:
    """Represents one of the three main categories: base, bonus, or penalty."""
    def __init__(self, name, max_score=100):
        self.name = name
        self.max_score = max_score
        self.subjects: dict[str, Subject] = {}

    def set_weight(self, weight):
        self.max_score = weight

    def add_subject(self, subject: Subject):
        self.subjects[subject.name] = subject

    def __repr__(self):
        return f"TestCategory(name='{self.name}', max_score={self.max_score},subjects={list(self.subjects.keys())})"


class Criteria:
    """The ROOT of the criteria tree."""
    def __init__(self, bonus_weight=0, penalty_weight=0):
        self.base = TestCategory("base")
        self.bonus = TestCategory("bonus", max_score=bonus_weight)
        self.penalty = TestCategory("penalty", max_score=penalty_weight)

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
        print(f"{prefix}📁 {category.name.upper()} (max_score: {category.max_score})")
        for subject in category.subjects.values():
            self._print_subject(subject, prefix=prefix + "    ")

    def _print_subject(self, subject: Subject, prefix: str):
        """Recursive helper method to print a subject and its contents."""
        print(f"{prefix}📘 {subject.name} (weight: {subject.weight})")

        if subject.subjects is not None:
            for sub in subject.subjects.values():
                self._print_subject(sub, prefix=prefix + "    ")

        if subject.tests is not None:
            for test in subject.tests:
                print(f"{prefix}  - 🧪 {test.name} (file: {test.file})")
                for call in test.calls:
                    print(f"{prefix}    - Parameters: {call.args}")

    def print_pre_executed_tree(self):
        """Prints a visual representation of the entire pre-executed criteria tree."""
        print(f"🌲 Pre-Executed Criteria Tree")
        self._print_pre_executed_category(self.base, prefix="  ")
        self._print_pre_executed_category(self.bonus, prefix="  ")
        self._print_pre_executed_category(self.penalty, prefix="  ")

    def _print_pre_executed_category(self, category: TestCategory, prefix: str):
        """Helper method to print a category and its pre-executed subjects."""
        if not category.subjects:
            return
        print(f"{prefix}📁 {category.name.upper()} (max_score: {category.max_score})")
        for subject in category.subjects.values():
            self._print_pre_executed_subject(subject, prefix=prefix + "    ")

    def _print_pre_executed_subject(self, subject: Subject, prefix: str):
        """Recursive helper method to print a subject and its pre-executed test results."""
        print(f"{prefix}📘 {subject.name} (weight: {subject.weight})")

        if subject.subjects is not None:
            for sub in subject.subjects.values():
                self._print_pre_executed_subject(sub, prefix=prefix + "    ")

        if subject.tests is not None:
            # In a pre-executed tree, subject.tests contains TestResult objects

            # In the regular tree, subject.tests contains "Test" objects
            for result in subject.tests:
                if isinstance(result, TestResult):
                    params_str = f" (Parameters: {result.parameters})" if result.parameters else ""
                    print(f"{prefix}  - 📝 {result.test_name}{params_str} -> Score: {result.score}")

                elif isinstance(result, Test):
                    print(f"{prefix} - 🧪 {result.name} (file: {result.file})")
                    """Added the symbol identificator to match the previous formatting"""
                    for call in result.calls:
                        print(f"{prefix}    - Parameters: {call.args}")
                else:
                    # Fallback for unexpected types
                    print(f"{prefix}  - ? Unexpected item in tests list: {result}")



