from typing import List, Dict, Any

from autograder.builder.models.criteria_tree import Criteria, Subject, Test, TestCall, TestResult
from autograder.builder.models.template import Template


class CriteriaTree:
    """A factory for creating a Criteria object from a configuration dictionary."""

    @staticmethod
    def build_pre_executed_tree(config_dict: dict, template: Template, submission_files: dict) -> Criteria:
        """ Builds a Criteria tree and pre-executes all tests, having leaves as TestResult objects."""
        criteria = Criteria()

        for category_name in ["base", "bonus", "penalty"]:
            if category_name in config_dict:
                category = getattr(criteria, category_name)
                category_data = config_dict[category_name]

                if "weight" in category_data:
                    category.max_score = category_data.get("weight", 100)

                if "subjects" in category_data:
                    subjects = [
                        CriteriaTree._parse_and_execute_subject(s_name, s_data, template, submission_files)
                        for s_name, s_data in category_data["subjects"].items()
                    ]
                    CriteriaTree._balance_subject_weights(subjects)
                    for subject in subjects:
                        category.add_subject(subject)
        return criteria

    @staticmethod
    def build_non_executed_tree(config_dict: dict) -> Criteria:
        """Builds the entire criteria tree, including balancing subject weights."""
        criteria = Criteria()

        for category_name in ["base", "bonus", "penalty"]:
            if category_name in config_dict:
                category = getattr(criteria, category_name)
                category_data = config_dict[category_name]

                # Set max_score for bonus and penalty categories
                if "weight" in category_data:
                    category.max_score = category_data.get("weight", 100)

                if "subjects" in category_data:
                    subjects = [
                        CriteriaTree._parse_subject(s_name, s_data)
                        for s_name, s_data in category_data["subjects"].items()
                    ]
                    CriteriaTree._balance_subject_weights(subjects)
                    for subject in subjects:
                        category.add_subject(subject)
        return criteria

    @staticmethod
    def _balance_subject_weights(subjects: List[Subject]):
        """Balances the weights of a list of sibling subjects to sum to 100."""
        total_weight = sum(s.weight for s in subjects)
        if total_weight > 0 and total_weight != 100:
            scaling_factor = 100 / total_weight
            for subject in subjects:
                subject.weight *= scaling_factor

    @staticmethod
    def _parse_subject(subject_name: str, subject_data: dict) -> Subject:
        """Recursively parses a subject and balances the weights of its children."""
        if "tests" in subject_data and "subjects" in subject_data:
            raise ValueError(f"Config error: Subject '{subject_name}' cannot have both 'tests' and 'subjects'.")

        subject = Subject(subject_name, subject_data.get("weight", 0))

        if "tests" in subject_data:
            subject.tests = CriteriaTree._parse_tests(subject_data["tests"])
        elif "subjects" in subject_data:
            child_subjects = [
                CriteriaTree._parse_subject(sub_name, sub_data)
                for sub_name, sub_data in subject_data["subjects"].items()
            ]
            CriteriaTree._balance_subject_weights(child_subjects)
            subject.subjects = {s.name: s for s in child_subjects}
        else:
            subject.tests = []
        return subject

    @staticmethod
    def _parse_and_execute_subject(subject_name: str, subject_data: dict, template: Template, submission_files: dict) -> Subject:
        """Recursively parses a subject, executes its tests, and balances the weights of its children."""
        if "tests" in subject_data and "subjects" in subject_data:
            raise ValueError(f"Config error: Subject '{subject_name}' cannot have both 'tests' and 'subjects'.")

        subject = Subject(subject_name, subject_data.get("weight", 0))

        if "tests" in subject_data:
            parsed_tests = CriteriaTree._parse_tests(subject_data["tests"])
            executed_tests = []
            for test in parsed_tests:
                # The run method executes the test and returns a list of TestResult objects
                test_results = test.run(template, submission_files, subject_name)
                executed_tests.extend(test_results)
            subject.tests = executed_tests  # Store TestResult objects instead of Test objects
        elif "subjects" in subject_data:
            child_subjects = [
                CriteriaTree._parse_and_execute_subject(sub_name, sub_data, template, submission_files)
                for sub_name, sub_data in subject_data["subjects"].items()
            ]
            CriteriaTree._balance_subject_weights(child_subjects)
            subject.subjects = {s.name: s for s in child_subjects}
        else:
            subject.tests = []
        return subject

    @staticmethod
    def _parse_tests(test_data: list) -> List[Test]:
        """Parses a list of test definitions from the configuration."""
        parsed_tests = []
        for test_item in test_data:
            if isinstance(test_item, str):
                # Handle simple test names (e.g., "check_no_unclosed_tags")
                test = Test(name=test_item, filename="index.html")  # Default file
                test.add_call(TestCall(args=[]))
                parsed_tests.append(test)

            elif isinstance(test_item, dict):
                # Handle complex test definitions
                test_name = test_item.get("name")
                test_file = test_item.get("file")
                if not test_name or not test_file:
                    raise ValueError(f"Test definition is missing 'name' or 'file': {test_item}")

                test = Test(name=test_name, filename=test_file)

                if "calls" in test_item:
                    for call_args in test_item["calls"]:
                        test.add_call(TestCall(args=call_args))
                else:
                    # If no 'calls' are specified, it's a single call with no arguments
                    test.add_call(TestCall(args=[]))

                parsed_tests.append(test)

        return parsed_tests