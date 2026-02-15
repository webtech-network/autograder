from autograder.models.result_tree import (
    CategoryResultNode,
    ResultTree,
    RootResultNode,
    SubjectResultNode,
    TestResultNode,
)
from autograder.utils.formatters.result_tree import ResultTreeFormatter
from autograder.utils.printers.printer import Printer


class ResultTreePrinter:
    def __init__(
        self,
        show_details: bool | None = True,
        formatter: ResultTreeFormatter | None = None,
        printer: Printer | None = None,
    ) -> None:
        self.__show_details = show_details
        self.__formatter = ResultTreeFormatter() if formatter is None else formatter
        self.__printer = Printer() if printer is None else printer

    def print_tree(self, tree: ResultTree):
        """
        Print a visual representation of the result tree.

        Args:
            show_details: If True, show test parameters and reports
        """
        self.__printer.print_lines(self.__formatter.header())

        # Print header info
        if tree.template_name:
            self.__printer.print(self.__formatter.template_name(tree.template_name))

        self.__printer.print(self.__formatter.final_score(tree.root.score))

        self.__printer.print(self.__formatter.resume(tree))
        self.__printer.print(self.__formatter.secondary_divisor())

        # Print tree structure
        self._print_root(tree.root)

        self.__printer.print(self.__formatter.main_divisor())

    def _print_root(self, root: RootResultNode):
        """Print the root node and its categories."""
        for category in root.get_all_categories():
            self._print_category(category)

    def _print_category(self, category: CategoryResultNode):
        """Print a category node."""
        self.__printer.print(self.__formatter.format_category(category))
        self.__print_children(category)

    def __print_children(
        self, parent: "SubjectResultNode | CategoryResultNode"
    ) -> None:
        for subject in parent.subjects:
            self._print_subject(subject)

        for test in parent.tests:
            self._print_test(test)

    def _print_subject(self, subject: SubjectResultNode):
        """Print a subject node."""
        self.__printer.increase_depth()
        self.__printer.print(self.__formatter.format_subject(subject))
        self.__print_children(subject)
        self.__printer.decrease_depth()

    def _print_test(self, test: TestResultNode) -> None:
        """Print a test result node."""

        self.__printer.print(self.__formatter.format_test(test))
        if self.__show_details:
            self.__printer.print_lines(self.__formatter.format_test_details(test))

    def print_summary(self, tree: ResultTree):
        """Print a compact summary of the results."""
        self.__printer.print_lines(self.__formatter.summary_header())
        self.__printer.print(self.__formatter.final_score(tree.root.score))

        self.__printer.print_lines(self.__formatter.format_test_results(tree))
        self.__printer.print_lines(self.__formatter.format_failed_test_results(tree))

        self.__printer.print(self.__formatter.main_divisor())
