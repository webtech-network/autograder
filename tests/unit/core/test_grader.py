import unittest

# Assuming these classes are in your project structure
from autograder.services.criteria_tree_service import CriteriaTree, Criteria, Subject, Test, TestCall
from autograder.models.dataclass.result import Result
from autograder.models.dataclass.test_result import TestResult
from autograder.builder.models.template import Template
from autograder.builder.models.test_function import TestFunction
from autograder.services.grader_service import Grader

# ===============================================================
# Mock Template Library based on the new TestFunction model
# ===============================================================

class PassingTest(TestFunction):
    @property
    def name(self): return "passing_test"
    @property
    def description(self): return "A mock test that always passes."
    @property
    def parameter_description(self): return {}
    def execute(self, *args, **kwargs) -> TestResult:
        return TestResult(self.name, 100, "This test always passes.")

class FailingTest(TestFunction):
    @property
    def name(self): return "failing_test"
    @property
    def description(self): return "A mock test that always fails."
    @property
    def parameter_description(self): return {}
    def execute(self, *args, **kwargs) -> TestResult:
        return TestResult(self.name, 0, "This test always fails.")

class PartialTest(TestFunction):
    @property
    def name(self): return "partial_test"
    @property
    def description(self): return "A mock test that gives partial credit."
    @property
    def parameter_description(self): return {}
    def execute(self, *args, **kwargs) -> TestResult:
        return TestResult(self.name, 50, "This test gives partial credit.")

class MockTemplate(Template):
    @property
    def name(self):
        return "Mock Library"

    def __init__(self):
        self.tests = {
            "passing_test": PassingTest(),
            "failing_test": FailingTest(),
            "partial_test": PartialTest(),
        }

    def get_test(self, name: str) -> TestFunction:
        return self.tests.get(name)

# ===============================================================
# Updated Unit Test Class
# ===============================================================

class TestGrader(unittest.TestCase):

    def setUp(self):
        """
        Set up a common mock library and submission data for the tests.
        """
        self.mock_library = MockTemplate()
        self.submission_files = {"index.html": "<html></html>"}
        self.author_name = "Test Student"

    def test_basic_score_calculation(self):
        """
        Tests the final score calculation with a mix of passing and failing tests.
        """
        config = {
            "base": {
                "subjects": {
                    "html": {
                        "weight": 100,
                        "tests": [
                            {"file": "index.html", "name": "passing_test"},
                            {"file": "index.html", "name": "failing_test"}
                        ]
                    }
                }
            }
        }
        criteria = CriteriaTree.build(config)
        grader = Grader(criteria, self.mock_library)
        result = grader.run(self.submission_files, self.author_name)
        # Average of tests: (100 + 0) / 2 = 50. Subject score = 50.
        self.assertAlmostEqual(result.final_score, 50)

    def test_bonus_points_application(self):
        """
        Tests that bonus points are correctly applied to the final score.
        """
        config = {
            "base": {
                "subjects": {"html": {"tests": [{"file": "index.html", "name": "partial_test"}]}}
            },
            "bonus": {
                "weight": 20, # This is the max_score for the bonus category
                "subjects": {"extra": {"tests": [{"file": "index.html", "name": "passing_test"}]}}
            }
        }
        criteria = CriteriaTree.build(config)
        grader = Grader(criteria, self.mock_library)
        result = grader.run(self.submission_files, self.author_name)

        # Base score = 50. Bonus score = 100.
        # Bonus points to add = (100 / 100) * 20 = 20.
        # Final score = 50 + 20 = 70.
        self.assertAlmostEqual(result.final_score, 70)

    def test_penalty_points_deduction(self):
        """
        Tests that penalty points are correctly deducted from the final score.
        A "failing" penalty test (score=0) means the penalty IS applied.
        """
        config = {
            "base": {
                "subjects": {"html": {"tests": [{"file": "index.html", "name": "passing_test"}]}}
            },
            "penalty": {
                "weight": 30, # This is the max_score for the penalty category
                "subjects": {"malpractice": {"tests": [{"file": "index.html", "name": "failing_test"}]}}
            }
        }
        criteria = CriteriaTree.build(config)
        grader = Grader(criteria, self.mock_library)
        result = grader.run(self.submission_files, self.author_name)

        # Base score = 100.
        # Penalty test failed (score=0), so 100% of the penalty is incurred.
        # Penalty points to subtract = (100 / 100) * 30 = 30.
        # Final score = 100 - 30 = 70.
        self.assertAlmostEqual(result.final_score, 70)

    def test_complex_grading_with_nested_subjects(self):
        """
        Tests the grader with a more complex, nested criteria tree with varying weights.
        """
        config = {
            "base": {
                "subjects": {
                    "frontend": {
                        "weight": 80,
                        "subjects": {
                            "html": {"weight": 50, "tests": [{"file": "index.html", "name": "passing_test"}]}, # Score: 100
                            "css": {"weight": 50, "tests": [{"file": "index.html", "name": "failing_test"}]}  # Score: 0
                        }
                    },
                    "backend": {
                        "weight": 20,
                        "tests": [{"file": "index.html", "name": "partial_test"}] # Score: 50
                    }
                }
            }
        }
        criteria = CriteriaTree.build(config)
        grader = Grader(criteria, self.mock_library)
        result = grader.run(self.submission_files, self.author_name)

        # Frontend score (weighted avg of children) = (100 * 0.5) + (0 * 0.5) = 50
        # Backend score = 50
        # Total base score (weighted avg of children) = (50 * 0.8) + (50 * 0.2) = 40 + 10 = 50
        self.assertAlmostEqual(result.final_score, 50)
        self.assertIsInstance(result, Result)
        self.assertEqual(len(grader.base_results), 3)

if __name__ == '__main__':
    unittest.main()