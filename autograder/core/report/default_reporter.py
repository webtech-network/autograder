"""Default Reporter module."""

from autograder.builder.models.template import Template
from autograder.core.models.feedback_preferences import FeedbackPreferences
from autograder.core.report.base_reporter import BaseReporter


class DefaultReporter(BaseReporter):
    """
    Generates a structured and visually appealing markdown feedback report
    designed to be a clear and helpful learning tool for students.
    """

    def __init__(
        self,
        result: "Result",
        feedback: "FeedbackPreferences",
        test_library: "Template",
    ):
        super().__init__(result, feedback, test_library)
        self.test_library = test_library

    def generate_feedback(self) -> str:
        """
        Builds the entire markdown report by assembling its various sections.
        """
        report_parts = [
            self._build_header(),
            self._build_category_section("bonus"),
            self._build_category_section("base"),
            self._build_category_section("penalty"),
        ]

        if self.feedback.general.add_report_summary:
            summary = self._build_summary()
            if summary:  # Only add summary if it's not empty
                report_parts.append(summary)

        report_parts.append(self._build_footer())
        return "\n".join(filter(None, report_parts))

    def _format_parameters(self, params: dict) -> str:
        """Helper function to format parameters into a readable code string."""
        if not params:
            return ""
        parts = [
            f"`{k}`: `{v}`" if isinstance(v, str) else f"`{k}`: `{v}`"
            for k, v in params.items()
        ]
        return f" (Parâmetros: {', '.join(parts)})"

    def _build_header(self) -> str:
        """Constructs the top section of the report."""
        header_parts = [f"# {self.feedback.general.report_title}"]
        if self.feedback.general.show_score:
            header_parts.append(
                f"> **Nota Final:** **`{self.result.final_score:.2f} / 100`**"
            )

        header_parts.append(
            f"\nOlá, **{self.result.author}**! 👋\n\nAqui está o feedback detalhado sobre sua atividade. Use este guia para entender seus acertos e os pontos que podem ser melhorados."
        )
        return "\n".join(header_parts)

    def _build_category_section(self, category_name: str) -> str:
        """Builds a report section for a specific category with enhanced formatting and text."""
        category_results = getattr(self.result, f"{category_name}_results", [])
        header = self.feedback.default.category_headers.get(
            category_name, category_name.capitalize()
        )
        section_parts = [f"\n---\n\n## {header}"]

        results_to_show = []
        intro_text = ""
        is_bonus = False

        if category_name == "bonus":
            is_bonus = True
            if self.feedback.general.show_passed_tests:
                results_to_show = [res for res in category_results if res.score >= 60]
                intro_text = (
                    "Parabéns! Você completou os seguintes itens bônus, demonstrando um ótimo conhecimento:"
                    if results_to_show
                    else "Nenhum item bônus foi completado desta vez. Continue se desafiando!"
                )
        else:  # base and penalty
            results_to_show = [res for res in category_results if res.score < 60]
            if category_name == "base":
                intro_text = (
                    "Encontramos alguns pontos nos requisitos essenciais que precisam de sua atenção:"
                    if results_to_show
                    else "Excelente! Todos os requisitos essenciais foram atendidos com sucesso."
                )
            elif category_name == "penalty":
                intro_text = (
                    "Foram detectadas algumas práticas que resultaram em penalidades. Veja os detalhes abaixo para entender como corrigi-las:"
                    if results_to_show
                    else "Ótimo trabalho! Nenhuma má prática foi detectada no seu projeto."
                )

        section_parts.append(intro_text)

        if not results_to_show:
            return "\n".join(section_parts)

        grouped_results = self._group_results_by_subject(results_to_show)

        for subject, results in grouped_results.items():
            section_parts.append(
                f"\n#### Tópico: {subject.replace('_', ' ').capitalize()}"
            )
            for res in results:
                params_str = self._format_parameters(res.parameters)

                if is_bonus:
                    status_text = "✅ **Passou**"
                    report_prefix = "Parabéns!"
                else:
                    status_text = "❌ **Falhou**"
                    report_prefix = (
                        "Atenção:" if category_name == "base" else "Cuidado!"
                    )

                feedback_item = [
                    f"> {status_text} no teste `{res.test_name}`{params_str}",
                    f"> - **Detalhes:** {report_prefix} {res.report}\n",
                ]

                if not is_bonus:
                    linked_content = self._content_map.get(res.test_name)
                    if linked_content:
                        feedback_item.append(
                            f"> - 📚 **Recurso Sugerido:** [{linked_content.description}]({linked_content.url})\n"
                        )

                section_parts.append("\n".join(feedback_item))

        return "\n".join(section_parts)

    def _build_summary(self) -> str:
        """Constructs the final summary section of the report using a markdown table."""
        summary_parts = ["\n---\n\n### 📝 Resumo dos Pontos de Atenção"]
        failed_base = [res for res in self.result.base_results if res.score < 100]
        failed_penalty = [res for res in self.result.penalty_results if res.score < 100]

        if not failed_base and not failed_penalty:
            return ""  # No need for a summary if everything is okay

        summary_parts.append("| Ação | Tópico | Detalhes do Teste |")
        summary_parts.append("|:---|:---|:---|")

        all_failed = failed_base + failed_penalty
        for res in all_failed:
            try:
                # Get the test function from the library to access its description
                test_func = self.test_library.get_test(res.test_name)
                description = test_func.description
            except AttributeError:
                description = "Descrição não disponível."

            params_str = (
                self._format_parameters(res.parameters)
                .replace(" (Parâmetros: ", "")
                .replace(")", "")
            )

            # Determine the action type
            action = "Revisar"
            if res in failed_penalty:
                action = "Corrigir (Penalidade)"

            # Build the detailed cell content
            details_cell = (
                f"**Teste:** `{res.test_name}`<br>"
                f"**O que foi verificado:** *{description}*<br>"
                f"**Parâmetros:** <sub>{params_str or 'N/A'}</sub>"
            )

            summary_parts.append(
                f"| {action} | `{res.subject_name}` | {details_cell} |"
            )

        return "\n".join(summary_parts)

    def _build_footer(self) -> str:
        """Constructs the footer of the report."""
        return (
            "\n---\n"
            + "> Continue praticando e melhorando seu código. Cada desafio é uma oportunidade de aprender! 🚀"
        )
