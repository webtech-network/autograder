import logging
from typing import List, Any, Dict
from autograder.context import request_context
from autograder.core.models.test_result import TestResult


logger = logging.getLogger(__name__)

# Assuming TestResult is defined in a separate, importable file
# from autograder.core.models.test_result import TestResult

# ===============================================================
# 1. Classes for Test Execution
# ===============================================================

# ===============================================================
# 2. Classes for the Tree Structure
# ===============================================================

class Test:
    """
    Represents a single test function with its parameters.
    This is a LEAF node in the grading tree.
    """
    def __init__(self, name: str, filename: str = None):
        self.name = name
        self.file = filename  # The file this test operates on (e.g., "index.html")
        self.parameters: Dict[str, Any] = {}

    def get_result(self, test_library, submission_files, subject_name: str) -> List[TestResult]:
        #pylint: disable=too-many-function-args
        """
        Retrieves a TestFunction object from the library and executes it with the parameters.
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
        # Execute the test with the parameters
        try:
            if file_content_to_pass is not None:
                # If parameters is a dict, pass as kwargs
                if isinstance(self.parameters, dict):
                    result = test_function_instance.execute(file_content_to_pass, **self.parameters)
                # If parameters is a list (old format), pass as args
                elif isinstance(self.parameters, list):
                    result = test_function_instance.execute(file_content_to_pass, *self.parameters)
                else:
                    result = test_function_instance.execute(file_content_to_pass)
            else:
                # No file content
                if isinstance(self.parameters, dict):
                    result = test_function_instance.execute(**self.parameters)
                elif isinstance(self.parameters, list):
                    result = test_function_instance.execute(*self.parameters)
                else:
                    result = test_function_instance.execute()
            
            result.subject_name = subject_name
            return [result]
        except TypeError as e:
            return [TestResult(self.name, 0, f"ERROR: Incorrect parameters for test '{self.name}': {e}", subject_name)]

    def __repr__(self):
        return f"Test(name='{self.name}', file='{self.file}', parameters={self.parameters})"

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
    """
    Represents one of the three main categories: base, bonus, or penalty.
    Can contain EITHER a list of tests OR a dictionary of subjects (not both).
    """
    def __init__(self, name, max_score=100):
        self.name = name
        self.max_score = max_score
        self.subjects: dict[str, Subject] | None = None
        self.tests: List[Test] | None = None

    def set_weight(self, weight):
        self.max_score = weight

    def add_subject(self, subject: Subject):
        if self.subjects is None:
            self.subjects = {}
        self.subjects[subject.name] = subject

    def __repr__(self):
        if self.tests is not None:
            return f"TestCategory(name='{self.name}', max_score={self.max_score}, tests={len(self.tests)})"
        return f"TestCategory(name='{self.name}', max_score={self.max_score}, subjects={list(self.subjects.keys()) if self.subjects else []})"


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
        logger.info("Criteria Tree")
        self._print_category(self.base, prefix="  ")
        self._print_category(self.bonus, prefix="  ")
        self._print_category(self.penalty, prefix="  ")

    def _print_category(self, category: TestCategory, prefix: str):
        """Helper method to print a category and its subjects or tests."""
        if not category.subjects and not category.tests:
            return
        print(f"{prefix}📁 {category.name.upper()} (max_score: {category.max_score})")
        
        if category.subjects:
            for subject in category.subjects.values():
                self._print_subject(subject, prefix=prefix + "    ")
        
        if category.tests:
            for test in category.tests:
                logger.info(f"    - {test.name} (file: {test.file})")
                if test.parameters:
                    logger.info(f"      - Parameters: {test.parameters}")

    def _print_subject(self, subject: Subject, prefix: str):
        """Recursive helper method to print a subject and its contents."""
        print(f"{prefix}📘 {subject.name} (weight: {subject.weight})")

        if subject.subjects is not None:
            for sub in subject.subjects.values():
                self._print_subject(sub, prefix=prefix + "    ")

        if subject.tests is not None:
            for test in subject.tests:
                logger.info(f"  - {test.name} (file: {test.file})")
                if test.parameters:
                    logger.info(f"    - Parameters: {test.parameters}")

    def print_pre_executed_tree(self):
        """Prints a visual representation of the entire pre-executed criteria tree."""
        logger.info("Pre-Executed Criteria Tree")
        self._print_pre_executed_category(self.base, prefix="  ")
        self._print_pre_executed_category(self.bonus, prefix="  ")
        self._print_pre_executed_category(self.penalty, prefix="  ")

    def _print_pre_executed_category(self, category: TestCategory, prefix: str):
        """Helper method to print a category and its pre-executed subjects or tests."""
        if not category.subjects and not category.tests:
            return
        print(f"{prefix}📁 {category.name.upper()} (max_score: {category.max_score})")
        
        if category.subjects:
            for subject in category.subjects.values():
                self._print_pre_executed_subject(subject, prefix=prefix + "    ")
        
        if category.tests:
            # In a pre-executed tree, category.tests contains TestResult objects
            for result in category.tests:
                if isinstance(result, TestResult):
                    params_str = f" (Parameters: {result.parameters})" if result.parameters else ""
                    logger.info(f"    - {result.test_name}{params_str} -> Score: {result.score}")
                else:
                    logger.info(f"    - Unexpected item in tests list: {result}")

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
                    logger.info(f"  - {result.test_name}{params_str} -> Score: {result.score}")

                elif isinstance(result, Test):
                    logger.info(f" - {result.name} (file: {result.file})")
                    """Added the symbol identificator to match the previous formatting"""
                    if result.parameters:
                        logger.info(f"    - Parameters: {result.parameters}")
                else:
                    # Fallback for unexpected types
                    logger.info(f"  - Unexpected item in tests list: {result}")



