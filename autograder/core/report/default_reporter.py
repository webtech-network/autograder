from autograder.builder.template_library.templates.web_dev import WebDevLibrary
from autograder.builder.tree_builder import custom_tree
from autograder.core.grading.grader import Grader
from autograder.core.models.feedback_preferences import FeedbackPreferences
from autograder.core.report.base_reporter import BaseReporter


# Assuming these classes are in their respective, importable files
# from .base_reporter import BaseReporter
# from autograder.core.models.feedback_preferences import FeedbackPreferences
# from autograder.core.models.result import Result
# from autograder.builder.tree_builder import TestResult





class DefaultReporter(BaseReporter):
    """
    Generates a structured and visually appealing markdown feedback report
    designed to be a clear and helpful learning tool for students.
    """

    def generate_feedback(self) -> str:
        """
        Builds the entire markdown report by assembling its various sections.
        """
        report_parts = [
            self._build_header(),
            self._build_category_section("bonus"),
            self._build_category_section("base"),
            self._build_category_section("penalty")
        ]

        if self.feedback.general.add_report_summary:
            report_parts.append(self._build_summary())

        report_parts.append(self._build_footer())
        return "\n".join(filter(None, report_parts))

    def _format_parameters(self, params: dict) -> str:
        """Helper function to format parameters into a readable code string."""
        if not params:
            return ""
        parts = [f"{k}: `{v}`" if isinstance(v, str) else f"{k}: {v}" for k, v in params.items()]
        return f" (Parâmetros: {', '.join(parts)})"

    def _build_header(self) -> str:
        """Constructs the top section of the report."""
        header_parts = [f"# {self.feedback.general.report_title}"]
        if self.feedback.general.show_score:
            header_parts.append(f"> **Nota Final:** **`{self.result.final_score:.2f} / 100`**")

        header_parts.append(
            f"\nOlá, **{self.result.author}**! 👋\n\nAqui está o feedback detalhado sobre sua atividade. Use este guia para entender seus acertos e os pontos que podem ser melhorados.")
        return "\n".join(header_parts)

    def _build_category_section(self, category_name: str) -> str:
        """Builds a report section for a specific category with enhanced formatting and text."""
        category_results = getattr(self.result, f"{category_name}_results", [])
        header = self.feedback.default.category_headers.get(category_name, category_name.capitalize())
        section_parts = [f"\n---\n\n## {header}"]

        results_to_show = []
        intro_text = ""
        is_bonus = False

        if category_name == "bonus":
            is_bonus = True
            if self.feedback.general.show_passed_tests:
                results_to_show = [res for res in category_results if res.score >= 100]
                intro_text = "Parabéns! Você completou os seguintes itens bônus, demonstrando um ótimo conhecimento:" if results_to_show else "Nenhum item bônus foi completado desta vez. Continue se desafiando!"
        else:  # base and penalty
            results_to_show = [res for res in category_results if res.score < 100]
            if category_name == "base":
                intro_text = "Encontramos alguns pontos nos requisitos essenciais que precisam de sua atenção:" if results_to_show else "Excelente! Todos os requisitos essenciais foram atendidos com sucesso."
            elif category_name == "penalty":
                intro_text = "Foram detectadas algumas práticas que resultaram em penalidades. Veja os detalhes abaixo para entender como corrigi-las:" if results_to_show else "Ótimo trabalho! Nenhuma má prática foi detectada no seu projeto."

        section_parts.append(intro_text)

        if not results_to_show:
            return "\n".join(section_parts)

        grouped_results = self._group_results_by_subject(results_to_show)

        for subject, results in grouped_results.items():
            section_parts.append(f"\n#### Tópico: {subject.replace('_', ' ').capitalize()}")
            for res in results:
                params_str = self._format_parameters(res.parameters)

                if is_bonus:
                    status_text = "✅ **Passou**"
                    report_prefix = "Parabéns!"
                else:
                    status_text = "❌ **Falhou**"
                    report_prefix = "Atenção:" if category_name == "base" else "Cuidado!"

                feedback_item = [
                    f"> {status_text} no teste `{res.test_name}`{params_str}",
                    f"> - **Detalhes:** {report_prefix} {res.report}\n\n"
                ]

                # Conditionally add learning resources ONLY for failed tests
                if not is_bonus:
                    linked_content = self._content_map.get(res.test_name)
                    if linked_content:
                        feedback_item.append(
                            f"> - 📚 **Recurso Sugerido:** [{linked_content.description}]({linked_content.url})\n\n")

                section_parts.append("\n".join(feedback_item))

        return "\n".join(section_parts)

    def _build_summary(self) -> str:
        """Constructs the final summary section of the report using a markdown table."""
        summary_parts = ["\n---\n\n### 📝 Resumo dos Pontos de Atenção"]
        failed_base = [res for res in self.result.base_results if res.score < 100]
        failed_penalty = [res for res in self.result.penalty_results if res.score < 100]

        if not failed_base and not failed_penalty:
            return ""  # No need for a summary if everything is okay

        summary_parts.append("| Ação | Tópico | Teste e Parâmetros |")
        summary_parts.append("|:---|:---|:---|")

        for res in failed_base:
            params_str = self._format_parameters(res.parameters).replace(" (Parâmetros: ", "").replace(")", "")
            summary_parts.append(f"| Revisar | `{res.subject_name}` | `{res.test_name}`<br><sub>{params_str}</sub> |")
        for res in failed_penalty:
            params_str = self._format_parameters(res.parameters).replace(" (Parâmetros: ", "").replace(")", "")
            summary_parts.append(
                f"| Corrigir (Penalidade) | `{res.subject_name}` | `{res.test_name}`<br><sub>{params_str}</sub> |")

        return "\n".join(summary_parts)

    def _build_footer(self) -> str:
        """Constructs the footer of the report."""
        return "\n---\n" + "> Continue praticando e melhorando seu código. Cada desafio é uma oportunidade de aprender! 🚀"

if __name__ == "__main__":
    feedback_config = {
        "general": {
            "report_title": "Relatório Final - Desafio Web",
            "add_report_summary": True,
            "online_content": [
                {
                    "url": "https://developer.mozilla.org/pt-BR/docs/Web/HTML/Element/img",
                    "description": "Guia completo sobre a tag <img>.",
                    "linked_tests": ["check_all_images_have_alt"]
                }
            ]
        },
        "ai": {
            "assignment_context": "Este é um desafio focado em HTML semântico e CSS responsivo.",
            "feedback_persona": "Professor Sênior"
        },
        "default": {
            "category_headers": {
                "base": "✔️ Requisitos Obrigatórios",
                "bonus": "🎉 Pontos Bônus",
                "penalty": "🚨 Pontos de Atenção"
            }
        }
    }

    # ===============================================================
    # 2. CREATE THE PREFERENCES OBJECT FROM THE DICTIONARY
    # ===============================================================
    # The .from_dict() method will parse the dictionary and fill in any missing
    # values with the defaults defined in the class.
    preferences = FeedbackPreferences.from_dict(feedback_config)

    # ===============================================================
    # 3. VERIFY THE PARSED VALUES
    # ===============================================================
    print("--- FeedbackPreferences object created successfully ---\n")

    # --- Verify General Preferences ---
    print("✅ General Preferences:")
    print(f"  - Report Title: '{preferences.general.report_title}' (Loaded from config)")
    print(f"  - Show Score: {preferences.general.show_score} (Using default value)")
    print(f"  - Online Content Items: {len(preferences.general.online_content)} (Loaded from config)")
    print(f"    - First item URL: {preferences.general.online_content[0].url}")
    print(f"    - Linked to tests: {preferences.general.online_content[0].linked_tests}")

    # --- Verify AI Preferences ---
    print("\n🤖 AI Reporter Preferences:")
    print(f"  - Feedback Persona: '{preferences.ai.feedback_persona}' (Loaded from config)")
    print(f"  - Feedback Tone: '{preferences.ai.feedback_tone}' (Using default value)")
    print(f"  - Assignment Context: '{preferences.ai.assignment_context}' (Loaded from config)")

    # --- Verify Default Reporter Preferences ---
    print("\n📝 Default Reporter Preferences:")
    print(f"  - Base Header: '{preferences.default.category_headers['base']}' (Loaded from config)")
    # 'bonus' was not in the config, so it should use the default from the class
    print(f"  - Bonus Header: '{preferences.default.category_headers['bonus']}' (Using default value)")
    root = custom_tree()
    grader = Grader(root, WebDevLibrary)
    submission_files = {
        "index.html": """
        <!DOCTYPE html>
        <html lang="pt-BR">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Página de Teste</title>
            <link rel="stylesheet" href="style.css">
        </head>
        <body>

            <header>
                <h1>Bem-vindo à Página de Teste</h1>
                <h3>Sub-cabeçalho H3</h3> </header>

            <main id="main-content">
                <p class="intro">Este é um parágrafo de introdução para testar o sistema.</p>

                <img src="image1.jpg" alt="Descrição da imagem 1">
                <img src="image2.jpg"> <div>
                    <p>Este é um div com um <font color="red">texto antigo</font> dentro.</p> </div>

                <a href="#">Este é um link de teste.</a>
            </main>


            <footer>
                <p>&copy; 2024 Autograder Test Page</p>
            </footer>

            <script src="script.js"></script>
        </body>
        </html>
        """,

        "style.css": """
        /* Arquivo CSS para Teste */

        body {
            font-family: sans-serif;
            color: #333; /* Passa no teste 'css_uses_property' */
        }

        #main-content {
            display: flex; /* Passa no teste 'css_uses_property' */
            width: 80%;
        }

        .intro {
            font-size: 16px;
            /* Penalidade: Uso de !important */
            color: navy !important; 
        }

        /* Penalidade: Regra de CSS vazia */
        .empty-rule {

        }
        """,

        "script.js": """
        // Arquivo JavaScript para Teste

        document.addEventListener('DOMContentLoaded', () => {
            const header = document.getElementById('main-content');
            console.log('Página carregada e script executado.');
        });

        // Penalidade: Uso do método proibido 'document.write'
        document.write("<p>Este texto foi adicionado com document.write</p>");

        // Teste de feature: usa arrow function
        const simpleFunction = () => {
            return true;
        };
        """
    }
    root.print_tree()
    result = grader.run(submission_files, "Arthur")
    print(result)
    reporter = DefaultReporter(result, preferences)
    report = reporter.generate_feedback()
    print(report)