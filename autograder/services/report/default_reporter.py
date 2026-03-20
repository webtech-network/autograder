

class DefaultReporter:
    def generate_report(self, focus, result_tree, preferences=None):
        """
        Generates a structured report using focus data, result tree, and preferences.
        """
        from autograder.utils.formatters.result_tree import ResultTreeFormatter
        formatter = ResultTreeFormatter()
        
        lines = []
        
        # 1. Title
        title = preferences.general.report_title if preferences else "Relatório de Avaliação"
        lines.extend([formatter.main_divisor(), title, formatter.main_divisor()])
        
        # 2. Summary (if requested)
        if preferences and preferences.general.add_report_summary and result_tree:
            lines.append("")
            lines.append("📊 RESUMO")
            if result_tree.template_name:
                lines.append(formatter.template_name(result_tree.template_name))
            lines.append(formatter.resume(result_tree))
            lines.append(formatter.secondary_divisor())

        # 3. Categorized Results (Base, Penalty, Bonus)
        if focus:
            show_passed = preferences.general.show_passed_tests if preferences else False
            category_headers = preferences.default.category_headers if preferences else {}
            
            categories = [
                ("base", focus.base, category_headers.get("base", "✅ Requisitos Essenciais")),
                ("penalty", focus.penalty, category_headers.get("penalty", "❌ Pontos a Melhorar")),
                ("bonus", focus.bonus, category_headers.get("bonus", "⭐ Pontos Extras"))
            ]
            
            for cat_id, tests, header in categories:
                if not tests:
                    continue
                
                # Filter tests based on preferences
                filtered_tests = [t for t in tests if show_passed or t.test_result.score < 100]
                
                if filtered_tests:
                    lines.append("")
                    lines.append(header)
                    for focused_test in filtered_tests:
                        test = focused_test.test_result
                        lines.append(formatter.format_test(test))
                        details = formatter.format_test_details(test)
                        if details:
                            lines.extend(details)

        # 4. Final Score (if requested)
        if preferences and preferences.general.show_score and result_tree:
            lines.append("")
            lines.append(formatter.main_divisor())
            lines.append(formatter.final_score(result_tree.root.score))
            lines.append(formatter.main_divisor())

        # 5. Online Resources
        if preferences and preferences.general.online_content:
            lines.append("")
            lines.append("📚 RECURSOS DE APRENDIZADO")
            for resource in preferences.general.online_content:
                lines.append(f"• {resource.description}: {resource.url}")

        return "\n".join(lines)
