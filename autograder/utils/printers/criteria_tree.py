from autograder.utils.formatters.criteria_tree import CriteriaTreeFormatter
from autograder.utils.printers.printer import Printer
from autograder.models.criteria_tree import CriteriaTree, CategoryNode, SubjectNode


class CriteriaTreePrinter:
    def __init__(
        self,
        formatter: CriteriaTreeFormatter | None = None,
        printer: Printer | None = None,
    ) -> None:
        self.__formatter = CriteriaTreeFormatter() if formatter is None else formatter
        self.__printer = Printer() if printer is None else printer

    def __print_children(self, parent: CategoryNode | SubjectNode) -> None:
        for subject in parent.subjects:
            self.print_subject(subject)

        for test in parent.tests:
            lines = self.__formatter.process_test(test)
            for line in lines:
                self.__printer.print(line)

    def print_subject(self, subject: SubjectNode) -> None:
        self.__printer.increase_depth()
        self.__printer.print(self.__formatter.process_subject(subject))
        self.__print_children(subject)
        self.__printer.decrease_depth()

    def print_category(self, category: CategoryNode) -> None:
        self.__printer.print(self.__formatter.process_category(category))
        self.__print_children(category)

    def print_tree(self, tree: CriteriaTree) -> None:
        self.__printer.print(self.__formatter.header())
        self.print_category(tree.base)
        if tree.bonus:
            self.print_category(tree.bonus)
        if tree.penalty:
            self.print_category(tree.penalty)
