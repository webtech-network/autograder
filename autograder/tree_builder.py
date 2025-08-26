from random import weibullvariate
from typing import List, Dict

from autograder.builder.models.criteria_tree import Criteria, TestCall, Test, Subject



class CriteriaTree:
    """A factory for creating a Criteria object from a configuration dictionary."""

    @staticmethod
    def build(config_dict: dict) -> Criteria:
        """
        Main entry point to build the entire criteria tree from a configuration dictionary.
        """
        criteria = Criteria()

        for category_name in ["base", "bonus", "penalty"]:
            if category_name in config_dict:
                category = getattr(criteria, category_name)
                category_data = config_dict[category_name]
                if "subjects" in category_data:
                    for subject_name, subject_data in category_data["subjects"].items():
                        category.add_subject(CriteriaTree._parse_subject(subject_name, subject_data))

        return criteria

    @staticmethod
    def _parse_subject(subject_name: str, subject_data: dict) -> Subject:
        """
        Recursively parses a subject. A subject can contain 'tests' OR nested 'subjects'.
        """
        if "tests" in subject_data and "subjects" in subject_data:
            raise ValueError(
                f"Configuration error: Subject '{subject_name}' cannot contain both 'tests' and 'subjects'.")

        subject = Subject(subject_name, subject_data.get("weight", 0))

        if "tests" in subject_data:
            subject.tests = CriteriaTree._parse_tests(subject_data["tests"])
        elif "subjects" in subject_data:
            subject.subjects = {
                sub_name: CriteriaTree._parse_subject(sub_name, sub_data)
                for sub_name, sub_data in subject_data["subjects"].items()
            }
        else:
            subject.tests = []

        return subject

    @staticmethod
    def _parse_tests(test_data: list) -> List[Test]:
        """
        Parses a list of tests from the JSON, grouping calls by test name.
        """
        tests_dict: Dict[str, Test] = {}

        for test_item in test_data:
            if isinstance(test_item, str):
                test_name = test_item
                if test_name not in tests_dict:
                    tests_dict[test_name] = Test(name=test_name)
                tests_dict[test_name].add_call(TestCall(args=[]))

            elif isinstance(test_item, dict):
                for test_name, calls_data in test_item.items():
                    if test_name not in tests_dict:
                        tests_dict[test_name] = Test(name=test_name)

                    for call_args in calls_data:
                        if isinstance(call_args, list):
                            tests_dict[test_name].add_call(TestCall(args=call_args))
                        elif isinstance(call_args, dict):
                            key, value = list(call_args.items())[0]
                            tests_dict[test_name].add_call(TestCall(args=[key, value]))
                        else:
                            tests_dict[test_name].add_call(TestCall(args=[call_args]))

        return list(tests_dict.values())


# ===============================================================
# 3. Example Usage
# ===============================================================

if __name__ == '__main__':
    example_config = {
        "base": {
            "subjects": {
                "html": {
                    "weight": 70,
                    "tests": [
                        {"has_tag": [["div", 50], ["span", 10]]},
                        "check_no_unclosed_tags"
                    ]
                },
                "css": {"weight": 30}
            }
        }
    }

    # Use the factory to build the tree
    criteria_tree_root = CriteriaTree.build(example_config)
    criteria_tree_root.print_tree()