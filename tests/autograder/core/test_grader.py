import unittest
from autograder.core.grading.grader import Grader
from autograder.builder.tree_builder import CriteriaTree
from autograder.core.models.test_result import TestResult
from autograder.core.models.result import Result

# Mock Test Library to simulate test execution
class MockTestLibrary:
    @staticmethod
    def passing_test(*args):
        return TestResult("passing_test", 100, "This test always passes.")

    @staticmethod
    def failing_test(*args):
        return TestResult("failing_test", 0, "This test always fails.")

    @staticmethod
    def partial_test(*args):
        return TestResult("partial_test", 50, "This test gives partial credit.")

class TestGrader(unittest.TestCase):

    def setUp(self):
        """
        Set up a common criteria tree and grader for the tests.
        """
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
                        "tests": ["passing_test", "failing_test"]
                    }
                }
            }
        }
        criteria = CriteriaTree.build(config)
        grader = Grader(criteria, MockTestLibrary)
        result = grader.run(self.submission_files, self.author_name)
        # (100 + 0) / 2 = 50
        self.assertAlmostEqual(result.final_score, 50)

    def test_bonus_points_application(self):
        """
        Tests that bonus points are correctly applied to the final score.
        """
        config = {
            "base": {
                "subjects": {"html": {"tests": ["partial_test"]}}
            },
            "bonus": {
                "weight": 20,
                "subjects": {"extra": {"tests": ["passing_test"]}}
            }
        }
        criteria = CriteriaTree.build(config)
        grader = Grader(criteria, MockTestLibrary)
        result = grader.run(self.submission_files, self.author_name)

        # Base score = 50. Bonus score = 100.
        # Bonus points = (100 / 100) * 20 = 20.
        # Final score = 50 + 20 = 70.
        self.assertAlmostEqual(result.final_score, 70)

    def test_penalty_points_deduction(self):
        """
        Tests that penalty points are correctly deducted from the final score.
        """
        config = {
            "base": {
                "subjects": {"html": {"tests": ["passing_test"]}}
            },
            "penalty": {
                "weight": 30,
                "subjects": {"malpractice": {"tests": ["passing_test"]}}
            }
        }
        criteria = CriteriaTree.build(config)
        grader = Grader(criteria, MockTestLibrary)
        result = grader.run(self.submission_files, self.author_name)

        # Base score = 100. Penalty score = 100.
        # Penalty deduction = (100 / 100) * 30 = 30.
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
                            "html": {"weight": 50, "tests": ["passing_test"]}, # Score: 100
                            "css": {"weight": 50, "tests": ["failing_test"]}  # Score: 0
                        }
                    },
                    "backend": {
                        "weight": 20,
                        "tests": ["partial_test"] # Score: 50
                    }
                }
            }
        }
        criteria = CriteriaTree.build(config)
        grader = Grader(criteria, MockTestLibrary)
        result = grader.run(self.submission_files, self.author_name)

        # Frontend score = (100 * 0.5) + (0 * 0.5) = 50
        # Backend score = 50
        # Total base score = (50 * 0.8) + (50 * 0.2) = 40 + 10 = 50
        self.assertAlmostEqual(result.final_score, 50)
        self.assertIsInstance(result, Result)
        self.assertEqual(len(grader.base_results), 3)

if __name__ == '__main__':
    unittest.main()