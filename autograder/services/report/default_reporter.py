from typing import Optional, List
from autograder.utils.formatters.result_tree import ResultTreeFormatter
from autograder.translations import t


class DefaultReporter:
    """Standard reporter that generates a human-readable markdown report."""

    def __init__(self):
        self._formatter = ResultTreeFormatter()

    def generate_report(self, focus, result_tree, preferences=None):
        """
        Generates a structured report using focus data, result tree, and preferences.
        """
        lines = []
        locale = preferences.locale if preferences else None

        # 1. Title
        lines.extend(self._add_title(preferences))

        # 2. Summary (if requested)
        if preferences and preferences.general.add_report_summary and result_tree:
            lines.extend(self._add_summary(result_tree, locale=locale))

        # 3. Categorized Results (Base, Penalty, Bonus)
        if focus:
            lines.extend(self._add_categorized_results(focus, preferences))

        # 4. Final Score (if requested)
        if preferences and preferences.general.show_score and result_tree:
            lines.extend(self._add_final_score(result_tree.root.score, locale=locale))

        # 5. Online Resources
        if preferences and preferences.general.online_content:
            lines.extend(self._add_online_resources(preferences.general.online_content, locale=locale))

        return "\n".join(lines)

    def _add_title(self, preferences):
        locale = preferences.locale if preferences else None
        default_title = t("feedback.report_title", locale=locale) or "Evaluation Report"
        title = preferences.general.report_title if preferences and preferences.general.report_title else default_title
        return [f"# {title}", ""]

    def _add_summary(self, result_tree, locale: Optional[str] = None):
        summary_header = t("feedback.report.summary_header", locale=locale) or "📊 SUMMARY"
        lines = [self._formatter.main_divisor(), f"## {summary_header}"]
        if result_tree.template_name:
            lines.append(self._formatter.template_name(result_tree.template_name, locale=locale))
        lines.append(self._formatter.resume(result_tree, locale=locale))
        return lines

    def _add_categorized_results(self, focus, preferences):
        lines = []
        locale = preferences.locale if preferences else None
        show_passed = preferences.general.show_passed_tests if preferences else False
        category_headers = preferences.default.category_headers if preferences else {}

        categories = [
            (focus.base, category_headers.get("base") or t("feedback.category.base", locale=locale) or "✅ Essential Requirements"),
            (focus.penalty, category_headers.get("penalty") or t("feedback.category.penalty", locale=locale) or "❌ Points to Improve"),
            (focus.bonus, category_headers.get("bonus") or t("feedback.category.bonus", locale=locale) or "⭐ Extra Points")
        ]

        for tests, header in categories:
            if not tests:
                continue

            filtered_tests = [t for t in tests if show_passed or t.test_result.score < 100]

            if filtered_tests:
                lines.append("")
                lines.append(self._formatter.main_divisor())
                lines.append(f"## {header}")
                for focused_test in filtered_tests:
                    test = focused_test.test_result
                    lines.append("")
                    lines.append(self._formatter.format_test(test))
                    details = self._formatter.format_test_details(test, locale=locale)
                    if details:
                        lines.extend(details)
        return lines

    def _add_final_score(self, score, locale: Optional[str] = None):
        final_score_label = t("feedback.report.final_score_label", locale=locale) or "🏆 Final Score"
        return [
            "",
            self._formatter.main_divisor(),
            f"## {final_score_label}",
            "",
            self._formatter.final_score(score)
        ]

    def _add_online_resources(self, resources, locale: Optional[str] = None):
        resources_label = t("feedback.report.learning_resources_label", locale=locale) or "📚 Learning Resources"
        lines = ["", self._formatter.main_divisor(), f"## {resources_label}", ""]
        for resource in resources:
            lines.append(f"- 📘 [{resource.description}]({resource.url})")
        return lines
