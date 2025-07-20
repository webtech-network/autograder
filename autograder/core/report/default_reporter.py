from autograder.core.report.base_reporter import BaseReporter
import json
from datetime import datetime
class DefaultReporter(BaseReporter):
    """Default reporter for test results.
    Checks for feedback texts from feedback.json"""
    @classmethod
    def get_key_value(cls,list, name):
        """
        :param list:
        :param name:
        :return:
        """
        for item in list:
            for key in item:
                if key == name:
                    return item[key]

    def generate_feedback(self,feedback_file="feedback.json"):
        """
        Generate a Markdown report for autograding feedback.
        Takes dictionaries for base, bonus, and penalty with keys `passed` and `failed` containing test names.

        :param base: Dictionary containing passed and failed validation for base checks.
        :param bonus: Dictionary containing passed and failed validation for bonus checks.
        :param author: String containing author name.
        :param penalty: Dictionary containing passed and failed validation for penalty checks.
        :param final_score: The final calculated score (provided as a parameter).
        :param feedback_file: Path to the JSON file containing test-specific feedback (default is "tests_feedback.json").
        :return: A Markdown formatted string with feedback.
        """



        # Load feedback data from the JSON file
        with open(feedback_file, "r", encoding="utf-8") as file:
            tests_feedback = json.load(file)
        passed = True if self.result.final_score >= 70 else False
        # Initialize feedback
        feedback = "<sup>Suas cotas de feedback AI acabaram, o sistema de feedback voltou ao padrão.</sup>\n\n"
        feedback += f"# 🧪 Relatório de Avaliação – Journey Levty Etapa 1 - {self.result.author}\n\n"
        feedback += f"**Data:** {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
        feedback += f"**Nota Final:** `{format(self.result.final_score, '.2f')}/100`\n"
        feedback += f"**Status:** {'✅ Aprovado' if passed else '❌ Reprovado'}\n\n"
        feedback += "---\n"

        # Base Feedback (Requisitos Obrigatórios)
        feedback += "## ✅ Requisitos Obrigatórios\n"
        if len(self.result.base_results["failed"]) == 0:
            feedback += "- Todos os requisitos básicos foram atendidos. Excelente trabalho!\n"
        else:
            feedback += f"- Foram encontrados `{len(self.result.base_results['failed'])}` problemas nos requisitos obrigatórios. Veja abaixo os testes que falharam:\n"
            for test_name in self.result.base_results["failed"]:
                # Get the feedback from the JSON structure based on pass/fail
                print("Test Name:", test_name)
                passed_feedback = self.get_key_value(tests_feedback["base_tests"], test_name)[1]  # Failed feedback
                feedback += f"  - ⚠️ **Falhou no teste**: `{test_name}`\n"
                feedback += f"    - **Melhoria sugerida**: {passed_feedback}\n"

        # Bonus Feedback
        feedback += "\n## ⭐ Itens de Destaque (recupera até 40 pontos)\n"
        if len(self.result.bonus_results["passed"]) > 0:
            feedback += f"- Você conquistou `{len(self.result.bonus_results['passed'])}` bônus! Excelente trabalho nos detalhes adicionais!\n"
            for passed_test in self.result.bonus_results["passed"]:
                # Get the feedback for passed bonus validation
                passed_feedback = self.get_key_value(tests_feedback["bonus_tests"], passed_test)[0]  # Failed feedback
                feedback += f"  - 🌟 **Testes bônus passados**: `{passed_test}`\n"
                feedback += f"    - {passed_feedback}\n"
        else:
            feedback += "- Nenhum item bônus foi identificado. Tente adicionar mais estilo e complexidade ao seu código nas próximas tentativas!\n"

        # Penalty Feedback
        feedback += "\n## ❌ Problemas Detectados (Descontos de até 100 pontos)\n"
        if len(self.result.penalty_results["passed"]) > 0:
            feedback += f"- Foram encontrados `{len(self.result.penalty_results['passed'])}` problemas que acarretam descontos. Veja abaixo os testes penalizados:\n"
            for failed_test in self.result.penalty_results["passed"]:
                # Get the feedback for failed penalty validation
                failed_feedback = self.get_key_value(tests_feedback["penalty_tests"], failed_test)[0]  # Failed feedback
                feedback += f"  - ⚠️ **Falhou no teste de penalidade**: `{failed_test}`\n"
                feedback += f"    - **Correção sugerida**: {failed_feedback}\n"
        else:
            feedback += "- Nenhuma infração grave foi detectada. Muito bom nesse aspecto!\n"

        feedback += "\n---\n"
        feedback += "Continue praticando e caprichando no código. Cada detalhe conta! 💪\n"
        feedback += "Se precisar de ajuda, não hesite em perguntar nos canais da guilda. Estamos aqui para ajudar! 🤝\n"
        feedback += "\n---\n"
        feedback += "<sup>Made By the Autograder Team.</sup><br>&nbsp;&nbsp;&nbsp;&nbsp;<sup><sup>- [Arthur Carvalho](https://github.com/ArthuCRodrigues)</sup></sup><br>&nbsp;&nbsp;&nbsp;&nbsp;<sup><sup>- [Arthur Drumond](https://github.com/drumondpucminas)</sup></sup><br>&nbsp;&nbsp;&nbsp;&nbsp;<sup><sup>- [Gabriel Resende](https://github.com/gnvr29)</sup></sup>"
        return feedback
