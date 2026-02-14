from typing import List
from autograder.models.result_tree import (
    CategoryResultNode,
    ResultTree,
    SubjectResultNode,
    TestResultNode,
)


class ResultTreeFormatter:
    def main_divisor(self):
        return "=" * 70

    def secondary_divisor(self) -> str:
        return "-" * 70

    def header(self) -> List[str]:
        return [self.main_divisor(), "🎯 RESULT TREE", self.main_divisor()]

    def summary_header(self) -> List[str]:
        return [self.main_divisor(), "📊 GRADING SUMMARY", self.main_divisor()]

    def resume(self, tree: ResultTree) -> str:
        return (
            f"📊 Tests: {len(tree.get_all_test_results())} total | "
            f"✅ {len(tree.get_passed_tests())} passed | "
            f"❌ {len(tree.get_failed_tests())} failed"
        )

    def template_name(self, template_name: str) -> str:
        return f"📋 Template: {template_name}"

    def final_score(self, score: float) -> str:
        return f"🏆 Final Score: {score:.2f}/100"

    def icon_score(self, score: float) -> str:
        if score >= 80:
            return "🟢"
        elif score >= 60:
            return "🟡"

        return "🔴"

    def format_category(self, category: CategoryResultNode) -> str:
        return (
            f"📘 {category.name.capitalize()} "
            f"[weight: {category.weight:.0f}%] "
            f"{self.icon_score(category.score)} {category.score:.1f}/100"
        )

    def format_subject(self, subject: SubjectResultNode) -> str:
        return (
            f"📘 {subject.name.capitalize()} "
            f"[weight: {subject.weight:.0f}%] "
            f"{self.icon_score(subject.score)} {subject.score:.1f}/100"
        )

    def format_test(self, test: TestResultNode) -> str:
        status = "✅" if test.score >= 100 else "❌"
        icon_score = self.icon_score(test.score)
        test_info = f"🧪 {test.name} {status}"

        if test.test_node.file_target:
            test_info += f" [file: {', '.join(test.test_node.file_target)}]"

        test_info += f" {icon_score} {test.score:.1f}/100"

        return test_info

    def format_test_details(self, test: TestResultNode) -> List[str]:
        result = []

        if test.parameters:
            params_str = ", ".join(f"{k}={v}" for k, v in test.parameters.items())
            result.append(f"    ⚙️  params: {params_str}")

        if test.report:
            result.append(f"    💬 {test.report}")

        return result

    def format_test_results(self, tree: ResultTree) -> List[str]:
        result = []

        all_tests = tree.get_all_test_results()
        passed = tree.get_passed_tests()
        failed = tree.get_failed_tests()

        result.append("📈 Test Results:")
        result.append(f"   Total:  {len(all_tests)}")
        result.append(
            f"   ✅ Passed: {len(passed)} ({len(passed) / len(all_tests) * 100:.1f}%)"
        )
        result.append(
            f"   ❌ Failed: {len(failed)} ({len(failed) / len(all_tests) * 100:.1f}%)"
        )

        avg_score = sum(t.score for t in all_tests) / len(all_tests)
        result.append(f"📊 Average Test Score: {avg_score:.2f}")

        return result

    def format_failed_test_results(self, tree: ResultTree) -> List[str]:
        result = []

        result.append("❌ Failed Tests:")
        for test in tree.get_failed_tests():
            result.append(f"   • {test.name}: {test.score:.1f}/100")
            if test.report:
                result.append(f"     {test.report}")

        return result
