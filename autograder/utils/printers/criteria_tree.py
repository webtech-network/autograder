from typing import TYPE_CHECKING
from autograder.utils.formatters.criteria_tree import CriteriaTreeFormatter

if TYPE_CHECKING:
    from autograder.models.criteria_tree import CriteriaTree, TestCategory, Subject


class CriteriaTreePrinter:
    def __init__(self, formatter: CriteriaTreeFormatter | None = None) -> None:
        self.__depth = 0
        self.__formatter = CriteriaTreeFormatter() if formatter is None else formatter

    def __increase_depth(self) -> None:
        self.__depth += 1

    def __decrease_depth(self) -> None:
        self.__depth -= 1

    def __print_with_depth(self, formatted: str) -> None:
        print(f"{'    ' * self.__depth}{formatted}")

    def __print_children(self, parent: "TestCategory | Subject") -> None:
        for subject in parent.subjects:
            self.print_subject(subject)

        for test in parent.tests:
            lines = self.__formatter.process_test(test)
            for line in lines:
                self.__print_with_depth(line)

    def print_subject(self, subject: "Subject") -> None:
        self.__increase_depth()
        self.__print_with_depth(self.__formatter.process_subject(subject))
        self.__print_children(subject)
        self.__decrease_depth()

    def print_category(self, category: "TestCategory") -> None:
        self.__print_with_depth(self.__formatter.process_category(category))
        self.__print_children(category)

    def print_tree(self, tree: "CriteriaTree") -> None:
        self.__print_with_depth(self.__formatter.header())
        self.print_category(tree.base)
        self.print_category(tree.bonus)
        self.print_category(tree.penalty)
