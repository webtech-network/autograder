from typing import List, override
from autograder.models.abstract.criteria_tree_processer import CriteriaTreeProcesser
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autograder.models.criteria_tree import CategoryNode, SubjectNode, TestNode


class CriteriaTreeFormatter(CriteriaTreeProcesser):
    def header(self) -> str:
        return "🌲 Criteria Tree"

    @override
    def process_test(self, test: "TestNode") -> List[str]:
        result: List[str] = []
        result.append(f"  🧪 {test.name} (file: {test.file_target})")
        result.append(f"    - Parameters: {test.parameters}")
        return result

    @override
    def process_subject(self, subject: "SubjectNode") -> str:
        return f"📘 {subject.name} (weight: {subject.weight})"

    @override
    def process_category(self, category: "CategoryNode") -> str:
        return f"  📁 {category.name.upper()} (max_score: {category.weight})"
