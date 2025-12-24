import unittest
from connectors.models.autograder_request import AutograderRequest
from connectors.models.assignment_config import AssignmentConfig
from autograder.context import request_context
from autograder.builder.tree_builder import CriteriaTree, Criteria, Subject, Test

class TestCriteriaTree(unittest.TestCase):

    def setUp(self):
        """Set up a fresh request context before each test."""
        request_context.set_request(None)
    
    def _create_request(self, criteria_config):
        """Helper to create a mock request with the given criteria config."""
        assignment_config = AssignmentConfig(
            criteria=criteria_config,
            feedback={}
        )
        request = AutograderRequest(
            student_name="Test Student",
            assignment_config=assignment_config,
            submission_files={}
        )
        request_context.set_request(request)

    def test_empty_config(self):
        """
        Tests that building a tree from an empty config results in an empty Criteria object.
        """
        config = {}
        self._create_request(config)
        criteria = CriteriaTree.build_non_executed_tree()
        self.assertIsInstance(criteria, Criteria)
        self.assertEqual(len(criteria.base.subjects) if criteria.base.subjects else 0, 0)

    def test_invalid_subject(self):
        """
        Tests that a ValueError is raised if a subject has both 'tests' and 'subjects'.
        """
        # Test with old format (dict)
        config_old = {
            "base": {
                "subjects": {
                    "invalid_subject": {
                        "tests": [{"file": "index.html", "name": "some_test"}],
                        "subjects": {"sub_subject": {}}
                    }
                }
            }
        }
        self._create_request(config_old)
        with self.assertRaises(ValueError):
            CriteriaTree.build_non_executed_tree()
        
        # Test with new format (array)
        config_new = {
            "base": {
                "subjects": [
                    {
                        "subject_name": "invalid_subject",
                        "tests": [{"file": "index.html", "name": "some_test"}],
                        "subjects": [{"subject_name": "sub_subject"}]
                    }
                ]
            }
        }
        self._create_request(config_new)
        with self.assertRaises(ValueError):
            CriteriaTree.build_non_executed_tree()

    def test_weight_balancing(self):
        """
        Tests that the weights of sibling subjects are correctly balanced to sum to 100.
        """
        config = {
            "base": {
                "subjects": {
                    "html": {"weight": 60, "tests": []},
                    "css": {"weight": 40, "tests": []}
                }
            },
            "bonus": {
                "weight": 50,
                "subjects": {
                    # These weights (10 + 10 = 20) will be scaled to sum to 100
                    "accessibility": {"weight": 10, "tests": []},
                    "performance": {"weight": 10, "tests": []}
                }
            }
        }
        self._create_request(config)
        criteria = CriteriaTree.build_non_executed_tree()

        # Check base subjects (already sum to 100)
        self.assertAlmostEqual(criteria.base.subjects["html"].weight, 60)
        self.assertAlmostEqual(criteria.base.subjects["css"].weight, 40)

        # Check bonus subjects (should be scaled: 10/20 -> 50, 10/20 -> 50)
        self.assertAlmostEqual(criteria.bonus.subjects["accessibility"].weight, 50)
        self.assertAlmostEqual(criteria.bonus.subjects["performance"].weight, 50)
        self.assertEqual(criteria.bonus.max_score, 50)

    def test_structure_and_defaults_with_new_format(self):
        """
        Tests the overall structure with the new format using parameters instead of calls.
        """
        config = {
            "base": {
                "subjects": [
                    {
                        "subject_name": "html",
                        "weight": 100,
                        "tests": [
                            # Test with no parameters
                            {"file": "index.html", "name": "test1"},
                            # Test with parameters
                            {
                                "file": "index.html",
                                "name": "test2",
                                "parameters": {"arg1": 1, "arg2": "value"}
                            },
                            # Simple string test
                            "test3"
                        ]
                    }
                ]
            },
            "penalty": {"weight": 75}
        }
        self._create_request(config)
        criteria = CriteriaTree.build_non_executed_tree()

        # Test category weights
        self.assertEqual(criteria.penalty.max_score, 75)
        self.assertEqual(criteria.bonus.max_score, 0)  # Default

        # Test subject structure
        self.assertIn("html", criteria.base.subjects)
        html_subject = criteria.base.subjects["html"]
        self.assertIsInstance(html_subject, Subject)

        # Test tests structure
        self.assertEqual(len(html_subject.tests), 3)

        # Find and verify test1
        test1 = next(t for t in html_subject.tests if t.name == "test1")
        self.assertEqual(test1.file, "index.html")
        self.assertEqual(test1.parameters, {})

        # Find and verify test2
        test2 = next(t for t in html_subject.tests if t.name == "test2")
        self.assertEqual(test2.file, "index.html")
        self.assertEqual(test2.parameters, {"arg1": 1, "arg2": "value"})

        # Find and verify test3 (simple string)
        test3 = next(t for t in html_subject.tests if t.name == "test3")
        self.assertIsNone(test3.file)
        self.assertEqual(test3.parameters, {})

    def test_array_based_parameters_format(self):
        """
        Tests the new array-based parameters format: [{"name": "...", "value": ...}]
        """
        config = {
            "base": {
                "subjects": [
                    {
                        "subject_name": "html",
                        "weight": 100,
                        "tests": [
                            {
                                "file": "index.html",
                                "name": "test_with_array_params",
                                "parameters": [
                                    {"name": "tag", "value": "div"},
                                    {"name": "count", "value": 5}
                                ]
                            }
                        ]
                    }
                ]
            }
        }
        self._create_request(config)
        criteria = CriteriaTree.build_non_executed_tree()

        html_subject = criteria.base.subjects["html"]
        test = html_subject.tests[0]
        
        # Parameters should be converted to dict
        self.assertEqual(test.parameters, {"tag": "div", "count": 5})
        self.assertIsInstance(test.parameters, dict)

    def test_array_based_parameters_edge_cases(self):
        """
        Tests edge cases for array-based parameters format.
        """
        # Test empty array
        config_empty = {
            "base": {
                "subjects": [
                    {
                        "subject_name": "html",
                        "weight": 100,
                        "tests": [
                            {
                                "file": "index.html",
                                "name": "test_empty_params",
                                "parameters": []
                            }
                        ]
                    }
                ]
            }
        }
        self._create_request(config_empty)
        criteria = CriteriaTree.build_non_executed_tree()
        test = criteria.base.subjects["html"].tests[0]
        self.assertEqual(test.parameters, {})

    def test_array_based_parameters_validation(self):
        """
        Tests that invalid array-based parameters raise proper errors.
        """
        # Test missing 'name' key
        config_missing_name = {
            "base": {
                "subjects": [
                    {
                        "subject_name": "html",
                        "weight": 100,
                        "tests": [
                            {
                                "file": "index.html",
                                "name": "test_invalid",
                                "parameters": [
                                    {"value": "div"}  # missing 'name'
                                ]
                            }
                        ]
                    }
                ]
            }
        }
        self._create_request(config_missing_name)
        with self.assertRaises(ValueError) as context:
            CriteriaTree.build_non_executed_tree()
        self.assertIn("must have both 'name' and 'value' keys", str(context.exception))

        # Test missing 'value' key
        config_missing_value = {
            "base": {
                "subjects": [
                    {
                        "subject_name": "html",
                        "weight": 100,
                        "tests": [
                            {
                                "file": "index.html",
                                "name": "test_invalid",
                                "parameters": [
                                    {"name": "tag"}  # missing 'value'
                                ]
                            }
                        ]
                    }
                ]
            }
        }
        self._create_request(config_missing_value)
        with self.assertRaises(ValueError) as context:
            CriteriaTree.build_non_executed_tree()
        self.assertIn("must have both 'name' and 'value' keys", str(context.exception))

    def test_backward_compatibility_with_calls(self):
        """
        Tests that the old 'calls' format is still supported for backward compatibility.
        """
        config = {
            "base": {
                "subjects": {
                    "html": {
                        "weight": 100,
                        "tests": [
                            {
                                "file": "index.html",
                                "name": "test_with_calls",
                                "calls": [
                                    ["arg1", 1],
                                    ["arg2", 2]
                                ]
                            }
                        ]
                    }
                }
            }
        }
        self._create_request(config)
        criteria = CriteriaTree.build_non_executed_tree()

        html_subject = criteria.base.subjects["html"]
        # With old format, multiple calls create multiple test instances
        tests_with_name = [t for t in html_subject.tests if t.name == "test_with_calls"]
        self.assertEqual(len(tests_with_name), 2)

    def test_complex_weight_balancing(self):
        """
        Tests weight balancing with a more complex, nested subject structure.
        """
        config = {
            "base": {
                "subjects": {
                    "frontend": {
                        "weight": 75,
                        "subjects": {
                            "html": {"weight": 50, "tests": []},
                            "css": {"weight": 50, "tests": []}
                        }
                    },
                    "backend": {
                        "weight": 25,
                        "subjects": {
                            # These weights (10 + 30 = 40) will be scaled to sum to 100
                            "database": {"weight": 10, "tests": []},
                            "api": {"weight": 30, "tests": []}
                        }
                    }
                }
            }
        }
        self._create_request(config)
        criteria = CriteriaTree.build_non_executed_tree()

        # Top-level subjects should not be re-balanced as they sum to 100
        self.assertAlmostEqual(criteria.base.subjects["frontend"].weight, 75)
        self.assertAlmostEqual(criteria.base.subjects["backend"].weight, 25)

        # Nested subjects in 'frontend' are already balanced
        frontend = criteria.base.subjects["frontend"]
        self.assertAlmostEqual(frontend.subjects["html"].weight, 50)
        self.assertAlmostEqual(frontend.subjects["css"].weight, 50)

        # Nested subjects in 'backend' should be re-balanced
        backend = criteria.base.subjects["backend"]
        self.assertAlmostEqual(backend.subjects["database"].weight, 25) # 10/40 -> 25
        self.assertAlmostEqual(backend.subjects["api"].weight, 75)      # 30/40 -> 75

if __name__ == '__main__':
    unittest.main()