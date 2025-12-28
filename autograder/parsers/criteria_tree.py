from typing import Any, Dict, List, Optional, override

from autograder.models.abstract.template import Template
from autograder.models.config.criteria import CriteriaConfig
from autograder.models.config.subject import SubjectConfig
from autograder.models.config.test import TestConfig
from autograder.models.criteria_tree import (
    CriteriaTree,
    Subject,
    Test,
    TestCall,
    TestCategory,
)
from autograder.models.dataclass.test_result import TestResult


class CriteriaTreeParser:
    def __parse_subjects(self, configs: Dict[str, SubjectConfig]) -> List[Subject]:
        subjects = [
            self.__parse_subject(s_name, s_data) for s_name, s_data in configs.items()
        ]
        self.__balance_subject_weights(subjects)
        return subjects

    def __parse_subject(self, name: str, config: SubjectConfig) -> Subject:
        subject = Subject(name)
        if config.weight:
            subject.weight = config.weight

        if config.subjects_weight:
            subject.subjects_weight = config.subjects_weight

        if config.subjects:
            subject.subjects = self.__parse_subjects(config.subjects)

        if config.tests:
            subject.tests = self.__parse_tests(config.tests)

        return subject

    def __balance_subject_weights(self, subjects: List[Subject]) -> None:
        total_weight = sum(s.weight for s in subjects)
        if total_weight > 0 and total_weight != 100:
            scaling_factor = 100 / total_weight
            for subject in subjects:
                subject.weight = round(subject.weight * scaling_factor)

    def __parse_tests(self, tests_data: List[TestConfig | str]) -> List[Test]:
        return [self.__parse_test(test_item) for test_item in tests_data]

    def __parse_test(self, test_item: TestConfig | str) -> Test:
        if isinstance(test_item, str):
            test_name = test_item
            test_file = None
            calls = None
        elif isinstance(test_item, TestConfig):
            test_name = test_item.name
            test_file = test_item.file
            calls = test_item.calls

        test = Test(test_name, test_file)
        if calls is not None:
            for call_args in calls:
                test.add_call(TestCall(call_args))
        else:
            test.add_call(TestCall([]))

        return test

    def __parse_category(self, category_name, config: SubjectConfig) -> TestCategory:
        category = TestCategory(category_name)

        if config.weight:
            category.max_score = config.weight

        if config.subjects:
            category.add_subjects(self.__parse_subjects(config.subjects))

        if config.tests:
            category.tests = self.__parse_tests(config.tests)

        return category

    def parse_tree(self, tree_data: Dict[str, Any]) -> CriteriaTree:
        tree = CriteriaTree()
        config = CriteriaConfig(**tree_data)

        for category_name in ["base", "bonus", "penalty"]:
            category_data = getattr(config, category_name)
            if category_data is None:
                continue
            parsed_category = self.__parse_category(category_name, category_data)
            setattr(tree, category_name, parsed_category)

        return tree


class PreExecutedTreeParser(CriteriaTreeParser):
    def __init__(self, template: Template, submission_files: Dict[str, str]) -> None:
        self.__template: Template = template
        self.__submission_files = submission_files
        self.__current_subject_name: Optional[str] = None

    @override
    def __parse_subject(self, name: str, config: SubjectConfig) -> Subject:
        self.__current_subject_name = name
        subject = super().__parse_subject(name, config)
        self.__current_subject_name = None
        return subject

    @override
    def __parse_tests(self, tests_data: List[TestConfig | str]) -> List[TestResult]:
        subject_name = self.__current_subject_name
        if subject_name is None:
            raise ValueError(
                "Failed to get subject_name during pre executed tree parsing"
            )
        tests = super().__parse_tests(tests_data)
        result = []
        for test in tests:
            executed_tests = test.get_result(
                self.__template, self.__submission_files, subject_name
            )
            result.extend(executed_tests)
        return result
