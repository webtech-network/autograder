import unittest
from autograder.builder.tree_builder import CriteriaTree, Criteria, Subject, Test, TestCall

class TestCriteriaTree(unittest.TestCase):

    def test_empty_config(self):
        """
        Tests that building a tree from an empty config results in an empty Criteria object.
        """
        config = {}
        criteria = CriteriaTree.build(config)
        self.assertIsInstance(criteria, Criteria)
        self.assertEqual(len(criteria.base.subjects), 0)
        self.assertEqual(len(criteria.bonus.subjects), 0)
        self.assertEqual(len(criteria.penalty.subjects), 0)

    def test_invalid_subject(self):
        """
        Tests that a ValueError is raised if a subject has both 'tests' and 'subjects'.
        """
        config = {
            "base": {
                "subjects": {
                    "invalid_subject": {
                        "tests": ["some_test"],
                        "subjects": {"sub_subject": {}}
                    }
                }
            }
        }
        with self.assertRaises(ValueError):
            CriteriaTree.build(config)

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
                    "accessibility": {"weight": 10, "tests": []},
                    "performance": {"weight": 10, "tests": []}
                }
            }
        }
        criteria = CriteriaTree.build(config)

        # Check base subjects (already sum to 100)
        self.assertAlmostEqual(criteria.base.subjects["html"].weight, 60)
        self.assertAlmostEqual(criteria.base.subjects["css"].weight, 40)

        # Check bonus subjects (should be scaled to sum to 100)
        self.assertAlmostEqual(criteria.bonus.subjects["accessibility"].weight, 50)
        self.assertAlmostEqual(criteria.bonus.subjects["performance"].weight, 50)

    def test_structure_and_defaults(self):
        """
        Tests the overall structure of the built tree and the application of default values.
        """
        config = {
            "base": {
                "subjects": {
                    "html": {
                        "tests": [
                            "test1",
                            {"test2": [["arg1", 1], "arg2"]}
                        ]
                    }
                }
            },
            "bonus": {"weight": 30}
        }
        criteria = CriteriaTree.build(config)

        # Test category weights
        self.assertEqual(criteria.bonus.max_score, 30)
        self.assertEqual(criteria.penalty.max_score, 100)  # Default

        # Test subject structure
        self.assertIn("html", criteria.base.subjects)
        html_subject = criteria.base.subjects["html"]
        self.assertIsInstance(html_subject, Subject)
        self.assertEqual(html_subject.weight, 0)  # Default weight

        # Test tests structure
        self.assertEqual(len(html_subject.tests), 2)
        test1 = next(t for t in html_subject.tests if t.name == "test1")
        test2 = next(t for t in html_subject.tests if t.name == "test2")
        self.assertIsInstance(test1, Test)
        self.assertEqual(len(test1.calls), 1)
        self.assertIsInstance(test1.calls[0], TestCall)
        self.assertEqual(test1.calls[0].args, [])

        self.assertEqual(len(test2.calls), 2)
        self.assertEqual(test2.calls[0].args, ["arg1", 1])
        self.assertEqual(test2.calls[1].args, ["arg2"])

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
                            "database": {"weight": 10, "tests": []},
                            "api": {"weight": 30, "tests": []}
                        }
                    }
                }
            }
        }
        criteria = CriteriaTree.build(config)

        # Top-level subjects should not be re-balanced as they sum to 100
        self.assertAlmostEqual(criteria.base.subjects["frontend"].weight, 75)
        self.assertAlmostEqual(criteria.base.subjects["backend"].weight, 25)

        # Nested subjects should be re-balanced within their parent
        frontend = criteria.base.subjects["frontend"]
        self.assertAlmostEqual(frontend.subjects["html"].weight, 50)
        self.assertAlmostEqual(frontend.subjects["css"].weight, 50)

        backend = criteria.base.subjects["backend"]
        self.assertAlmostEqual(backend.subjects["database"].weight, 25) # 10 -> 25
        self.assertAlmostEqual(backend.subjects["api"].weight, 75)      # 30 -> 75

if __name__ == '__main__':
    unittest.main()