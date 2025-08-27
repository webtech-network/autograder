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

def custom_tree():
    example_config = {
        "base": {
            "subjects": {
                "html": {
                    "tests": [
                        {"has_tag": [["div", 50], ["span", 10], ["h1", 10], ["h2", 10], ["h3", 10], ["p", 10]]},
                        {"has_attribute": [["class", 20], ["id", 20], ["src", 20], ["href", 20], ["alt", 20]]},
                        {"has_structure": ["header", "nav", "main", "section", "article", "footer"]},
                        "check_no_unclosed_tags",
                        "check_no_inline_styles",
                        "check_css_linked"
                    ]
                },
                "css": {
                    "weight": 30
                },
                "javascript": {
                    "weight": 20
                }
            }
        },
        "bonus": {
            "subjects": {
                "accessibility": {
                    "weight": 15,
                    "tests": [
                        {"has_attribute": [["aria-label", 10], ["role", 5], ["tabindex", 5]]},
                        "check_headings_sequential",
                        "check_all_images_have_alt"
                    ]
                },
                "advanced_features": {
                    "weight": 10,
                    "tests": [
                        {"css_uses_property": [["display", "grid"], ["--*", "css-variable"]]},
                        {"js_uses_feature": ["arrow_function", "template_literal", "let_const"]}
                    ]
                },
                "responsiveness": {
                    "weight": 5,
                    "tests": [
                        "check_has_media_queries",
                        "check_viewport_meta_tag"
                    ]
                }
            }
        },
        "penalty": {
            "subjects": {
                "html_validation": {
                    "weight": 10,
                    "tests": [
                        {"has_deprecated_tag": [["font", 5], ["center", 5], ["marquee", 10]]}
                    ]
                },
                "css_malpractice": {
                    "weight": 10,
                    "tests": [
                        {"count_usage": [["!important", 5]]}
                    ]
                },
                "js_malpractice": {
                    "weight": 15,
                    "tests": [
                        {"uses_forbidden_method": [["eval", 50], ["document.write", 20]]},
                        {"count_global_vars": [5]}
                    ]
                }
            }
        }
    }

    return CriteriaTree.build(example_config)
if __name__ == '__main__':
    root = custom_tree()
    root.print_tree()