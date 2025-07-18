from core.report.base_reporter import BaseReporter
from utils.path import Path
import json
from datetime import datetime

class DefaultReporter(BaseReporter):
    """Default reporter for test results.
    Checks for feedback texts from feedback.json"""

    @classmethod
    def get_key_value(cls, data_list, name):
        """
        Safely retrieves the value associated with a given key from a list of dictionaries.
        Returns None if the key or item is not found.
        :param data_list: A list of dictionaries.
        :param name: The key to search for.
        :return: The value associated with the key, or None if not found.
        """
        if not isinstance(data_list, list):
            return None

        for item in data_list:
            if isinstance(item, dict) and name in item:
                return item[name]
        return None

    def generate_feedback(self, feedback_file="feedback.json"):
        """
        Generate a Markdown report for autograding feedback.
        Takes dictionaries for base, bonus, and penalty with keys `passed` and `failed` containing test names.

        :param base: Dictionary containing passed and failed tests for base checks.
        :param bonus: Dictionary containing passed and failed tests for bonus checks.
        :param author: String containing author name.
        :param penalty: Dictionary containing passed and failed tests for penalty checks.
        :param final_score: The final calculated score (provided as a parameter).
        :param feedback_file: Path to the JSON file containing test-specific feedback (default is "tests_feedback.json").
        :return: A Markdown formatted string with feedback.
        """
        tests_feedback = {}
        try:
            with open(feedback_file, "r", encoding="utf-8") as file:
                tests_feedback = json.load(file)
        except FileNotFoundError:
            print(f"Warning: Feedback file '{feedback_file}' not found. No test-specific feedback will be included.")
        except json.JSONDecodeError:
            print(f"Warning: Could not decode JSON from '{feedback_file}'. No test-specific feedback will be included.")

        passed = True if self.result.final_score >= 70 else False
        # Initialize feedback
        feedback = "<sup>Suas cotas de feedback AI acabaram, o sistema de feedback voltou ao padrão.</sup>\n\n"
        feedback += f"# 🧪 Relatório de Avaliação – Journey Levty Etapa 1 - {getattr(self.result, 'author', 'N/A')}\n\n"
        feedback += f"**Data:** {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
        feedback += f"**Nota Final:** `{format(self.result.final_score, '.2f')}/100`\n"
        feedback += f"**Status:** {'✅ Aprovado' if passed else '❌ Reprovado'}\n\n"
        feedback += "---\n"

        # --- Base Feedback (Requisitos Obrigatórios) ---
        feedback += "## ✅ Requisitos Obrigatórios\n"
        base_failed_tests = self.result.base_results.get("failed", []) if hasattr(self.result, 'base_results') else []
        base_tests_feedback = tests_feedback.get("base_tests", [])

        if not base_failed_tests:
            feedback += "- Todos os requisitos básicos foram atendidos. Excelente trabalho!\n"
        else:
            feedback += f"- Foram encontrados `{len(base_failed_tests)}` problemas nos requisitos obrigatórios. Veja abaixo os testes que falharam:\n"
            for test_name in base_failed_tests:
                feedback_info = self.get_key_value(base_tests_feedback, test_name)
                # Ensure feedback_info is a list and has at least two elements before accessing index 1
                suggested_improvement = feedback_info[1] if isinstance(feedback_info, list) and len(feedback_info) > 1 else "Nenhuma sugestão de melhoria disponível."
                feedback += f"  - ⚠️ **Falhou no teste**: `{test_name}`\n"
                feedback += f"    - **Melhoria sugerida**: {suggested_improvement}\n"

        # --- Bonus Feedback ---
        feedback += "\n## ⭐ Itens de Destaque (recupera até 40 pontos)\n"
        bonus_passed_tests = self.result.bonus_results.get("passed", []) if hasattr(self.result, 'bonus_results') else []
        bonus_tests_feedback = tests_feedback.get("bonus_tests", [])

        if bonus_passed_tests:
            feedback += f"- Você conquistou `{len(bonus_passed_tests)}` bônus! Excelente trabalho nos detalhes adicionais!\n"
            for passed_test in bonus_passed_tests:
                feedback_info = self.get_key_value(bonus_tests_feedback, passed_test)
                # Ensure feedback_info is a list and has at least one element before accessing index 0
                bonus_description = feedback_info[0] if isinstance(feedback_info, list) and len(feedback_info) > 0 else "Nenhuma descrição de bônus disponível."
                feedback += f"  - 🌟 **Testes bônus passados**: `{passed_test}`\n"
                feedback += f"    - {bonus_description}\n"
        else:
            feedback += "- Nenhum item bônus foi identificado. Tente adicionar mais estilo e complexidade ao seu código nas próximas tentativas!\n"

        # --- Penalty Feedback ---
        feedback += "\n## ❌ Problemas Detectados (Descontos de até 100 pontos)\n"
        penalty_passed_tests = self.result.penalty_results.get("passed", []) if hasattr(self.result, 'penalty_results') else []
        penalty_tests_feedback = tests_feedback.get("penalty_tests", [])

        if penalty_passed_tests:
            feedback += f"- Foram encontrados `{len(penalty_passed_tests)}` problemas que acarretam descontos. Veja abaixo os testes penalizados:\n"
            for failed_test in penalty_passed_tests:
                feedback_info = self.get_key_value(penalty_tests_feedback, failed_test)
                # Ensure feedback_info is a list and has at least one element before accessing index 0
                penalty_suggestion = feedback_info[0] if isinstance(feedback_info, list) and len(feedback_info) > 0 else "Nenhuma sugestão de correção disponível."
                feedback += f"  - ⚠️ **Falhou no teste de penalidade**: `{failed_test}`\n"
                feedback += f"    - **Correção sugerida**: {penalty_suggestion}\n"
        else:
            feedback += "- Nenhuma infração grave foi detectada. Muito bom nesse aspecto!\n"

        feedback += "\n---\n"
        feedback += "Continue praticando e caprichando no código. Cada detalhe conta! 💪\n"
        feedback += "Se precisar de ajuda, não hesite em perguntar nos canais da guilda. Estamos aqui para ajudar! 🤝\n"
        feedback += "\n---\n"
        feedback += "<sup>Made By the Autograder Team.</sup><br>&nbsp;&nbsp;&nbsp;&nbsp;<sup><sup>- [Arthur Carvalho](https://github.com/ArthurCRodrigues)</sup></sup><br>&nbsp;&nbsp;&nbsp;&nbsp;<sup><sup>- [Arthur Drumond](https://github.com/drumondpucminas)</sup></sup><br>&nbsp;&nbsp;&nbsp;&nbsp;<sup><sup>- [Gabriel Resende](https://github.com/gnvr29)</sup></sup>"
        return feedback