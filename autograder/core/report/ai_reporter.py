import os

from openai import OpenAI

from autograder.builder.models.template import Template
from autograder.core.models.feedback_preferences import FeedbackPreferences
from autograder.core.report.base_reporter import BaseReporter


# Supondo que estas classes estão em seus respectivos arquivos e são importáveis
# from .base_reporter import BaseReporter
# from autograder.core.models.feedback_preferences import FeedbackPreferences
# from autograder.core.models.result import Result

class AIReporter(BaseReporter):
    """
    Gera um feedback sofisticado e humanizado, enviando um prompt detalhado
    para um modelo de IA.
    """

    def __init__(self, result: 'Result', feedback: 'FeedbackPreferences', test_library: 'Template', quota: int):
        super().__init__(result, feedback,test_library)
        openai_key = os.getenv("OPENAI_API_KEY")
        if not openai_key:
            raise ValueError("A chave da API da OpenAI é necessária para o AiReporter.")
        self.client = OpenAI(api_key=openai_key)
        self.quota = quota
        self.test_library = test_library

    def generate_feedback(self) -> str:
        """
        Constrói um prompt detalhado e chama o modelo de IA para gerar o feedback.
        """
        final_prompt = self._build_prompt()

        try:
            response = self.client.chat.completions.create(
                model="gpt-4",  # Ou outro modelo de sua escolha
                messages=[
                    {"role": "system", "content": self.feedback.ai.feedback_persona},
                    {"role": "user", "content": final_prompt}
                ],
                temperature=0.6)
            ai_generated_text = response.choices[0].message.content


        except Exception as e:
            ai_generated_text = f"**Ocorreu um erro ao gerar o feedback da IA:** {e}\n\nRetornando para o feedback padrão."

        # --- Formata o relatório final ---
        report_parts = [
            f"# {self.feedback.general.report_title}",
            f"<sup>Este é um feedback gerado por IA e pode conter erros. Você tem {self.quota} créditos restantes.</sup>",
            f"\nOlá, **{self.result.author}**! Aqui está um feedback detalhado sobre sua atividade.",
            f"> **Nota Final:** **`{self.result.final_score:.2f} / 100`**",
            "---",
            ai_generated_text  # O conteúdo principal vem da IA
        ]

        if self.feedback.general.add_report_summary:
            summary = self._build_summary()
            if summary:
                report_parts.append(summary)

        report_parts.append("\n\n---\n" + "> Caso queira tirar uma dúvida específica, entre em contato com o Chapter.")

        return "\n".join(filter(None, report_parts))

    def _format_parameters(self, params: dict) -> str:
        """Helper function to format parameters into a readable code string."""
        if not params:
            return ""
        parts = [f"`{k}`: `{v}`" if isinstance(v, str) else f"`{k}`: `{v}`" for k, v in params.items()]
        return f" (Parâmetros: {', '.join(parts)})"

    def _build_prompt(self) -> str:
        """Monta todas as informações necessárias em um único e grande prompt para a IA."""

        prompt_parts = [
            f"**Persona da IA:**\n{self.feedback.ai.feedback_persona}",
            f"**Contexto da Atividade:**\n{self.feedback.ai.assignment_context}",
            f"**Orientações Adicionais:**\n{self.feedback.ai.extra_orientations}",
            f"**Tom do Feedback:**\n{self.feedback.ai.feedback_tone}",
            f"**Nível de Ajuda com Soluções:**\n{self.feedback.ai.provide_solutions}",
            "---",
            self._get_submission_files_as_text(),
            "---",
            self._format_test_results_for_prompt(),
            "---",
            self._format_learning_resources_for_prompt(),
            "---",
            "**Sua Tarefa:**\nCom base em todo o contexto, código e resultados dos testes fornecidos, escreva um feedback em markdown que seja útil e educativo, seguindo todas as orientações."
        ]
        return "\n\n".join(filter(None, prompt_parts))

    def _get_submission_files_as_text(self) -> str:
        """Lê o conteúdo dos arquivos do aluno especificados nas preferências."""
        files_to_read = self.feedback.ai.submission_files_to_read
        if not files_to_read:
            return "**Código do Aluno:**\nNenhum arquivo foi especificado para leitura."

        file_contents = ["**Código do Aluno:**"]
        for filename in files_to_read:
            content = self.result.submission_files.get(filename, f"Arquivo '{filename}' não encontrado.")
            file_contents.append(f"\n---\n`{filename}`\n---\n```\n{content}\n```")

        return "\n".join(file_contents)

    def _format_test_results_for_prompt(self) -> str:
        """Formata os resultados dos testes em uma string para a IA analisar."""
        results_parts = ["**Resultados dos Testes para Análise:**"]

        failed_base = [res for res in self.result.base_results if res.score < 100]
        passed_bonus = [res for res in self.result.bonus_results if res.score >= 100]
        failed_penalty = [res for res in self.result.penalty_results if res.score < 100]

        if failed_base:
            results_parts.append("\n**Testes Obrigatórios que Falharam (Erros Críticos):**")
            for res in failed_base:
                results_parts.append(
                    f"- Teste: `{res.test_name}`, Parâmetros: `{res.parameters}`, Mensagem: {res.report}")

        if passed_bonus and self.feedback.general.show_passed_tests:
            results_parts.append("\n**Testes Bônus Concluídos com Sucesso (Elogiar):**")
            for res in passed_bonus:
                results_parts.append(f"- Teste: `{res.test_name}`, Parâmetros: `{res.parameters}`")

        if failed_penalty:
            results_parts.append("\n**Penalidades Aplicadas (Más Práticas Detectadas):**")
            for res in failed_penalty:
                results_parts.append(
                    f"- Teste: `{res.test_name}`, Parâmetros: `{res.parameters}`, Mensagem: {res.report}")

        return "\n".join(results_parts)

    def _format_learning_resources_for_prompt(self) -> str:
        """Formata o conteúdo online para que a IA saiba qual link sugerir para cada erro."""
        if not self.feedback.general.online_content:
            return ""

        resource_parts = [
            "**Recursos de Aprendizagem Disponíveis:**\nSe um teste que falhou estiver listado abaixo, sugira o link correspondente."]

        for resource in self.feedback.general.online_content:
            tests = ", ".join(f"`{t}`" for t in resource.linked_tests)
            resource_parts.append(
                f"- Se os testes {tests} falharem, recomende este link: [{resource.description}]({resource.url})")

        return "\n".join(resource_parts)

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
                print("Looking for mother function of test:", res.test_name)
                print(self.test_library)
                print("Available tests in library:", self.test_library.template_name)
                test_func = self.test_library.get_test(res.test_name)
                print("Testing function:", test_func.name)
                description = test_func.description
            except AttributeError:
                description = "Descrição não disponível."

            params_str = self._format_parameters(res.parameters).replace(" (Parâmetros: ", "").replace(")", "")

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

            summary_parts.append(f"| {action} | `{res.subject_name}` | {details_cell} |")

        return "\n".join(summary_parts)

    def _get_mock_ai_response(self) -> str:
        """Uma resposta mockada para fins de teste, já que não estamos fazendo uma chamada de API real."""
        return (
            "### Análise Geral\n"
            "Seu projeto está bem estruturado, mas notei alguns pontos de atenção, principalmente relacionados à acessibilidade das imagens e à responsividade.\n\n"
            "#### Pontos a Melhorar\n"
            "> **Acessibilidade de Imagens**\n"
            "> Percebi que uma de suas imagens está sem o atributo `alt`. Este atributo é fundamental para que leitores de tela possam descrever a imagem para usuários com deficiência visual. Analisando seu `index.html`, a segunda tag `<img>` precisa ser corrigida.\n\n"
            "> **Responsividade com Media Queries**\n"
            "> Seu CSS não inclui `@media` queries. Sem elas, seu layout não conseguirá se adaptar a telas menores, como as de celulares. Recomendo fortemente a leitura do material sobre Media Queries para implementar essa funcionalidade."
        )

    @classmethod
    def create(cls, result: 'Result', feedback: 'FeedbackPreferences', quota: int, test_library: 'Template'):
        response = cls(result, feedback, quota, test_library)
        return response
