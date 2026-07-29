from typing import List
from autograder.models.dataclass.focus import Focus, FocusedTest
from autograder.models.result_tree import (
    CategoryResultNode,
    ResultTree,
    TestResultNode,
)


class FocusService:
    """
    Service responsible for identifying the most impactful tests for student feedback.
    """
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

    def __process_category(self, category: CategoryResultNode) -> List[FocusedTest]:
        focused_tests: List[FocusedTest] = []

        for _path, test, multiplier in category.iter_test_results():
            focused_tests.append(
                FocusedTest(
                    test_result=test,
                    diff_score=self.__calculate_impact(test, multiplier),
                )
            )

        focused_tests.sort(
            key=lambda focused_test: focused_test.diff_score, reverse=True
        )

        return focused_tests

    def find(self, result_tree: ResultTree) -> Focus:
        """
        Find and prioritize impactful tests from the result tree.
        """
        return Focus(
            base=self.__process_category(result_tree.root.base),
            penalty=self.__process_category(result_tree.root.penalty)
            if result_tree.root.penalty is not None
            else None,
            bonus=self.__process_category(result_tree.root.bonus)
            if result_tree.root.bonus is not None
            else None,
        )
