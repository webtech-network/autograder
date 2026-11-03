"""Markdown fragments for the default feedback report."""
from typing import List, Optional

from autograder.models.contracts.outcome import ResultOutcomeTree, TestOutcome
from autograder.models.contracts.scoring import iter_tests
from autograder.translations import t


class ResultTreeFormatter:
    """Formats assessed criteria from the canonical result tree as Markdown."""

    def main_divisor(self) -> str:
        """Returns a major section separator."""
        return "---"

    def resume(self, tree: ResultOutcomeTree, locale: Optional[str] = None) -> str:
        """Returns a summarized test result with icons."""
        tests_label = t("feedback.report.tests_label", locale=locale) or "Tests"
        passed_label = t("feedback.report.passed_label", locale=locale) or "passed"
        failed_label = t("feedback.report.failed_label", locale=locale) or "failed"
        scores = [test.score for _, test in iter_tests(tree)]
        passed = sum(1 for score in scores if score >= 100)

        return (
            f"- 📊 **{tests_label}:** {len(scores)} total  \n"
            f"  - ✅ {passed} {passed_label}  \n"
            f"  - ❌ {len(scores) - passed} {failed_label}"
        )

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

    def format_test(self, test: TestOutcome) -> str:
        """Formats a single test result as an H3 header with status."""
        status = self.icon_status(test.score)
        return f"### 🧪 {test.name} {status}"

    def format_test_details(self, test: TestOutcome, locale: Optional[str] = None) -> List[str]:
        """Formats test details (file, score, params, report) as bullet points."""
        result = []
        icon_score = self.icon_score(test.score)

        if test.file_target:
            file_label = t("feedback.report.file_label", locale=locale) or "File"
            result.append(f"- 📁 **{file_label}:** `{', '.join(test.file_target)}`")

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
