from typing import List
from autograder.models.result_tree import (
    CategoryResultNode,
    ResultTree,
    SubjectResultNode,
    TestResultNode,
)


class ResultTreeFormatter:
    """Formatter that converts ResultTree data into modern, well-formatted Markdown."""

    def main_divisor(self) -> str:
        """Returns a major section separator."""
        return "---"

    def secondary_divisor(self) -> str:
        """Returns a secondary section separator."""
        return ""  # Not used in modern Markdown style but kept for compatibility

    def header(self) -> List[str]:
        """Returns the main header for the result tree."""
        return [self.main_divisor(), "# 🎯 RESULT TREE", self.main_divisor()]

    def resume(self, tree: ResultTree) -> str:
        """Returns a summarized test result with icons."""
        return (
            f"- 📊 **Tests:** {len(tree.get_all_test_results())} total  \n"
            f"  - ✅ {len(tree.get_passed_tests())} passed  \n"
            f"  - ❌ {len(tree.get_failed_tests())} failed"
        )

    def template_name(self, template_name: str) -> str:
        """Returns the formatted template name."""
        return f"- 📋 **Template:** `{template_name}`"

    def final_score(self, score: float) -> str:
        """Returns the formatted final score as a blockquote."""
        return f"> **{score:.2f} / 100**"

    def icon_score(self, score: float) -> str:
        """Returns an emoji based on the score range."""
        if score >= 80:
            return "🟢"
        if score >= 60:
            return "🟡"
        return "🔴"

    def icon_status(self, score: float) -> str:
        """Returns a status icon based on the score."""
        return "✅" if score >= 100 else "❌"

    def format_test(self, test: TestResultNode) -> str:
        """Formats a single test result as an H3 header with status."""
        status = self.icon_status(test.score)
        return f"### 🧪 {test.name} {status}"

    def format_test_details(self, test: TestResultNode) -> List[str]:
        """Formats test details (file, score, params, report) as bullet points."""
        result = []
        icon_score = self.icon_score(test.score)

        if test.test_node.file_target:
            result.append(f"- 📁 **Arquivo:** `{', '.join(test.test_node.file_target)}`")

        result.append(f"- {icon_score} **Nota:** {test.score:.1f}/100")

        if test.parameters:
            params_str = ", ".join(f"{k}={v}" for k, v in test.parameters.items())
            result.append(f"- ⚙️ **Parâmetros:** `{params_str}`")

        if test.report:
            label = "Erro" if test.score < 100 else "Feedback"
            result.append(f"- 💬 **{label}:** {test.report}")

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
