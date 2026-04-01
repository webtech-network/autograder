from typing import List, Optional
from autograder.models.result_tree import (
    CategoryResultNode,
    ResultTree,
    SubjectResultNode,
    TestResultNode,
)
from autograder.translations import t


class ResultTreeFormatter:
    """Formatter that converts ResultTree data into modern, well-formatted Markdown."""

    def main_divisor(self) -> str:
        """Returns a major section separator."""
        return "---"

    def secondary_divisor(self) -> str:
        """Returns a secondary section separator."""
        return ""  # Not used in modern Markdown style but kept for compatibility

    def header(self, locale: Optional[str] = None) -> List[str]:
        """Returns the main header for the result tree."""
        header_text = t("feedback.report.header", locale=locale) or "🎯 RESULT TREE"
        return [self.main_divisor(), f"# {header_text}", self.main_divisor()]

    def summary_header(self, locale: Optional[str] = None) -> List[str]:
        """Returns the header for the grading summary."""
        summary_text = t("feedback.report.summary_header", locale=locale) or "📊 GRADING SUMMARY"
        return [self.main_divisor(), f"## {summary_text}", self.main_divisor()]

    def resume(self, tree: ResultTree, locale: Optional[str] = None) -> str:
        """Returns a summarized test result with icons."""
        tests_label = t("feedback.report.tests_label", locale=locale) or "Tests"
        passed_label = t("feedback.report.passed_label", locale=locale) or "passed"
        failed_label = t("feedback.report.failed_label", locale=locale) or "failed"
        
        return (
            f"- 📊 **{tests_label}:** {len(tree.get_all_test_results())} total  \n"
            f"  - ✅ {len(tree.get_passed_tests())} {passed_label}  \n"
            f"  - ❌ {len(tree.get_failed_tests())} {failed_label}"
        )

    def template_name(self, template_name: str, locale: Optional[str] = None) -> str:
        """Returns the formatted template name."""
        template_label = t("feedback.report.template_label", locale=locale) or "Template"
        return f"- 📋 **{template_label}:** `{template_name}`"

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

    def format_category(self, category: CategoryResultNode, locale: Optional[str] = None) -> str:
        """Formats a category result node."""
        weight_label = t("feedback.report.weight_label", locale=locale) or "weight"
        return (
            f"## 📘 {category.name.capitalize()} "
            f"[{weight_label}: {category.weight:.0f}%] "
            f"{self.icon_score(category.score)} {category.score:.1f}/100"
        )

    def format_subject(self, subject: SubjectResultNode, locale: Optional[str] = None) -> str:
        """Formats a subject result node."""
        weight_label = t("feedback.report.weight_label", locale=locale) or "weight"
        return (
            f"### 📘 {subject.name.capitalize()} "
            f"[{weight_label}: {subject.weight:.0f}%] "
            f"{self.icon_score(subject.score)} {subject.score:.1f}/100"
        )

    def format_test(self, test: TestResultNode) -> str:
        """Formats a single test result as an H3 header with status."""
        status = self.icon_status(test.score)
        return f"### 🧪 {test.name} {status}"

    def format_test_details(self, test: TestResultNode, locale: Optional[str] = None) -> List[str]:
        """Formats test details (file, score, params, report) as bullet points."""
        result = []
        icon_score = self.icon_score(test.score)

        if test.test_node.file_target:
            file_label = t("feedback.report.file_label", locale=locale) or "File"
            result.append(f"- 📁 **{file_label}:** `{', '.join(test.test_node.file_target)}`")

        score_label = t("feedback.report.score_label", locale=locale) or "Score"
        result.append(f"- {icon_score} **{score_label}:** {test.score:.1f}/100")

        if test.parameters:
            params_label = t("feedback.report.params_label", locale=locale) or "Parameters"
            params_str = ", ".join(f"{k}={v}" for k, v in test.parameters.items())
            result.append(f"- ⚙️ **{params_label}:** `{params_str}`")

        if test.report:
            error_label = t("feedback.report.error_label", locale=locale) or "Error"
            feedback_label = t("feedback.report.feedback_label", locale=locale) or "Feedback"
            label = error_label if test.score < 100 else feedback_label
            result.append(f"- 💬 **{label}:** {test.report}")

        return result

    def format_test_results(self, tree: ResultTree, locale: Optional[str] = None) -> List[str]:
        """Formats overall test statistics."""
        result = []
        all_tests = tree.get_all_test_results()
        passed = tree.get_passed_tests()
        failed = tree.get_failed_tests()

        stats_header = t("feedback.report.stats_header", locale=locale) or "Test Statistics"
        total_label = t("feedback.report.total_label", locale=locale) or "Total"
        passed_label = t("feedback.report.passed_count_label", locale=locale) or "Passed"
        failed_label = t("feedback.report.failed_count_label", locale=locale) or "Failed"
        avg_label = t("feedback.report.avg_score_label", locale=locale) or "Average Score"

        result.append(f"### 📈 {stats_header}")
        result.append(f"- **{total_label}:** {len(all_tests)}")
        result.append(
            f"- ✅ **{passed_label}:** {len(passed)} ({len(passed) / len(all_tests) * 100:.1f}%)"
        )
        result.append(
            f"- ❌ **{failed_label}:** {len(failed)} ({len(failed) / len(all_tests) * 100:.1f}%)"
        )

        avg_score = sum(t_node.score for t_node in all_tests) / len(all_tests)
        result.append(f"- 📊 **{avg_label}:** {avg_score:.2f}")

        return result

    def format_failed_test_results(self, tree: ResultTree, locale: Optional[str] = None) -> List[str]:
        """Formats a summary of failed tests."""
        result = []
        failed_tests = tree.get_failed_tests()

        if failed_tests:
            failed_header = t("feedback.report.failed_tests_header", locale=locale) or "Failed Tests"
            result.append(f"### ❌ {failed_header}")
            for test in failed_tests:
                result.append(f"- **{test.name}:** {test.score:.1f}/100")
                if test.report:
                    result.append(f"  - 💬 {test.report}")

        return result
