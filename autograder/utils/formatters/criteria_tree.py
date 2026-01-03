from typing import List, override
from autograder.utils.processers.criteria_tree import CriteriaTreeProcesser
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autograder.models.dataclass.test_result import TestResult
    from autograder.models.criteria_tree import TestCategory, Subject, Test


class CriteriaTreeFormatter(CriteriaTreeProcesser):
    def header(self) -> str:
        return "🌲 Criteria Tree"

    @override
    def process_test(self, test: "Test") -> List[str]:
        result: List[str] = list()
        result.append(f"  🧪 {test.name} (file: {test.file})")
        for call in test.calls:
            result.append(f"    - Parameters: {call.args}")
        return result

    @override
    def process_subject(self, subject: "Subject") -> str:
        return f"📘{subject.name} (weight: {subject.weight})"

    @override
    def process_category(self, category: "TestCategory") -> str:
        return f"  📁 {category.name.upper()} (max_score: {category.max_score})"


class PreExecutedTreeFormatter(CriteriaTreeFormatter):
    @override
    def header(self) -> str:
        return "🌲 Pre-Executed Criteria Tree"

    @override
    def process_test(self, test: "Test | TestResult") -> List[str]:
        if isinstance(test, TestResult):
            if test.parameters:
                params = f" (Parameters: {test.parameters})"
            else:
                params = ""
            return [f"  - 📝 {test.test_name}{params} -> Score: {test.score}"]

        return super().process_test(test)
