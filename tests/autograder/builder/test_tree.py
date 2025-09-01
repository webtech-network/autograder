import unittest
# Assuming your tree builder and models are in this path
from autograder.builder.tree_builder import CriteriaTreeFactory, Criteria, Subject, Test, TestCall

class TestCriteriaTree(unittest.TestCase):

    def test_empty_config(self):
        """
        Tests that building a tree from an empty config results in an empty Criteria object.
        """
        config = {}
        criteria = CriteriaTreeFactory.build(config)
        self.assertIsInstance(criteria, Criteria)
        self.assertEqual(len(criteria.base.subjects), 0)

    def test_invalid_subject(self):
        """
        Tests that a ValueError is raised if a subject has both 'tests' and 'subjects'.
        """
        config = {
            "base": {
                "subjects": {
                    "invalid_subject": {
                        "tests": [{"file": "index.html", "name": "some_test"}],
                        "subjects": {"sub_subject": {}}
                    }
                }
            }
        }
        with self.assertRaises(ValueError):
            CriteriaTreeFactory.build(config)

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
        criteria = CriteriaTreeFactory.build(config)

        # Check base subjects (already sum to 100)
        self.assertAlmostEqual(criteria.base.subjects["html"].weight, 60)
        self.assertAlmostEqual(criteria.base.subjects["css"].weight, 40)

        # Check bonus subjects (should be scaled: 10/20 -> 50, 10/20 -> 50)
        self.assertAlmostEqual(criteria.bonus.subjects["accessibility"].weight, 50)
        self.assertAlmostEqual(criteria.bonus.subjects["performance"].weight, 50)
        self.assertEqual(criteria.bonus.max_score, 50)

    def test_structure_and_defaults_with_new_format(self):
        """
        Tests the overall structure with the new explicit test format.
        """
        config = {
            "base": {
                "subjects": {
                    "html": {
                        "tests": [
                            # Test with no calls
                            {"file": "index.html", "name": "test1"},
                            # Test with calls
                            {
                                "file": "index.html",
                                "name": "test2",
                                "calls": [["arg1", 1], ["arg2"]]
                            },
                            # Simple string test (should get a default file)
                            "test3"
                        ]
                    }
                }
            },
            "penalty": {"weight": 75}
        }
        criteria = CriteriaTreeFactory.build(config)

        # Test category weights
        self.assertEqual(criteria.penalty.max_score, 75)
        self.assertEqual(criteria.bonus.max_score, 100)  # Default

        # Test subject structure
        self.assertIn("html", criteria.base.subjects)
        html_subject = criteria.base.subjects["html"]
        self.assertIsInstance(html_subject, Subject)
        #self.assertEqual(html_subject.weight, 100)  # Default weight when it's the only subject

        # Test tests structure
        self.assertEqual(len(html_subject.tests), 3)

        # Find and verify test1
        test1 = next(t for t in html_subject.tests if t.name == "test1")
        self.assertEqual(test1.file, "index.html")
        self.assertEqual(len(test1.calls), 1)
        self.assertEqual(test1.calls[0].args, [])

        # Find and verify test2
        test2 = next(t for t in html_subject.tests if t.name == "test2")
        self.assertEqual(test2.file, "index.html")
        self.assertEqual(len(test2.calls), 2)
        self.assertEqual(test2.calls[0].args, ["arg1", 1])
        self.assertEqual(test2.calls[1].args, ["arg2"])

        # Find and verify test3 (simple string)
        test3 = next(t for t in html_subject.tests if t.name == "test3")
        self.assertEqual(test3.file, "index.html") # Check default file assignment
        self.assertEqual(len(test3.calls), 1)
        self.assertEqual(test3.calls[0].args, [])

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
        criteria = CriteriaTreeFactory.build(config)

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