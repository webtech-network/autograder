from autograder.utils.formatters.result_tree import ResultTreeFormatter


class DefaultReporter:
    """Standard reporter that generates a human-readable markdown report."""

    def __init__(self):
        self._formatter = ResultTreeFormatter()

    def generate_report(self, focus, result_tree, preferences=None):
        """
        Generates a structured report using focus data, result tree, and preferences.
        """
        lines = []

        # 1. Title
        lines.extend(self._add_title(preferences))

        # 2. Summary (if requested)
        if preferences and preferences.general.add_report_summary and result_tree:
            lines.extend(self._add_summary(result_tree))

        # 3. Categorized Results (Base, Penalty, Bonus)
        if focus:
            lines.extend(self._add_categorized_results(focus, preferences))

        # 4. Final Score (if requested)
        if preferences and preferences.general.show_score and result_tree:
            lines.extend(self._add_final_score(result_tree.root.score))

        # 5. Online Resources
        if preferences and preferences.general.online_content:
            lines.extend(self._add_online_resources(preferences.general.online_content))

        return "\n".join(lines)

    def _add_title(self, preferences):
        title = preferences.general.report_title if preferences else "Relatório de Avaliação"
        return [f"# {title}", ""]

    def _add_summary(self, result_tree):
        lines = [self._formatter.main_divisor(), "## 📊 RESUMO"]
        if result_tree.template_name:
            lines.append(self._formatter.template_name(result_tree.template_name))
        lines.append(self._formatter.resume(result_tree))
        return lines

    def _add_categorized_results(self, focus, preferences):
        lines = []
        show_passed = preferences.general.show_passed_tests if preferences else False
        category_headers = preferences.default.category_headers if preferences else {}

        categories = [
            (focus.base, category_headers.get("base", "✅ Requisitos Essenciais")),
            (focus.penalty, category_headers.get("penalty", "❌ Pontos a Melhorar")),
            (focus.bonus, category_headers.get("bonus", "⭐ Pontos Extras"))
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
                    details = self._formatter.format_test_details(test)
                    if details:
                        lines.extend(details)
        return lines

    def _add_final_score(self, score):
        return [
            "",
            self._formatter.main_divisor(),
            "## 🏆 Nota Final",
            "",
            self._formatter.final_score(score)
        ]

    def _add_online_resources(self, resources):
        lines = ["", self._formatter.main_divisor(), "## 📚 Recursos de Aprendizado", ""]
        for resource in resources:
            lines.append(f"- 📘 [{resource.description}]({resource.url})")
        return lines
