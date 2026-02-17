from typing import List, Optional
from autograder.models.dataclass.focus import Focus, FocusedTest
from autograder.models.result_tree import (
    CategoryResultNode,
    ResultTree,
    SubjectResultNode,
    TestResultNode,
)


class FocusService:
    def __calculate_impact(
        self, test: TestResultNode, cumulative_multiplier: float
    ) -> float:
        """
        Calculates how many points this specific test deducted from the
        absolute root total (0-100 scale).
        """
        if test.score == 100:
            return 0.0

        points_missed = 100 - test.score
        return points_missed * (test.weight / 100) * cumulative_multiplier

    def __process_subject(
        self, subject: SubjectResultNode, parent_multiplier: float
    ) -> List[FocusedTest]:
        focused_tests = list()

        # Determine the multiplier for children of this subject
        # If this subject has sub-subjects and tests, we might need to split the weight
        current_subject_multiplier = parent_multiplier
        current_test_multiplier = parent_multiplier

        if subject.subjects_weight is not None:
            # If subjects_weight is defined, it splits the pie between
            # Sub-Subjects group and Tests group.

            # The 'weight' of the sub-subjects group
            subj_group_w = subject.subjects_weight / 100
            # The 'weight' of the tests group
            test_group_w = (100 - subject.subjects_weight) / 100

            current_subject_multiplier *= subj_group_w
            current_test_multiplier *= test_group_w

        for child_subject in subject.subjects:
            # The child subject's weight contributes to the 'Subjects Group'
            child_weight_factor = child_subject.weight / 100
            focused_tests.extend(
                self.__process_subject(
                    child_subject, current_subject_multiplier * child_weight_factor
                )
            )

        for test in subject.tests:
            # The test's weight contributes to the 'Tests Group'
            focused_tests.append(
                FocusedTest(
                    test_result=test,
                    diff_score=self.__calculate_impact(test, current_test_multiplier),
                )
            )

        return focused_tests

    def __process_category(self, category: CategoryResultNode) -> List[FocusedTest]:
        focused_tests: List[FocusedTest] = list()

        # Initial Multiplier for a Category Root is 1.0 (100%)
        # Logic follows the same split as Subject if subjects_weight exists
        subj_mult = 1.0
        test_mult = 1.0

        if category.subjects_weight is not None:
            subj_mult = category.subjects_weight / 100
            test_mult = (100 - category.subjects_weight) / 100

        for subject in category.subjects:
            child_weight_factor = subject.weight / 100
            focused_tests.extend(
                self.__process_subject(subject, subj_mult * child_weight_factor)
            )

        for test in category.tests:
            focused_tests.append(
                FocusedTest(
                    test_result=test,
                    diff_score=self.__calculate_impact(test, test_mult),
                )
            )

        focused_tests.sort(
            key=lambda focused_test: focused_test.diff_score, reverse=True
        )

        return focused_tests

    def find(self, result_tree: ResultTree) -> Focus:
        return Focus(
            base=self.__process_category(result_tree.root.base),
            penalty=self.__process_category(result_tree.root.penalty)
            if result_tree.root.penalty is not None
            else None,
            bonus=self.__process_category(result_tree.root.bonus)
            if result_tree.root.bonus is not None
            else None,
        )
