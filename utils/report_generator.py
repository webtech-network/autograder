import json
import os
from datetime import datetime
from typing import final

from utils.path import Path
def get_key_value(list, name):
    """

    :param list:
    :param name:
    :return:
    """
    for item in list:
        for key in item:
            if key == name:
                return item[key]
def generate_md(base, bonus, penalty,final_score,author,feedback_file="feedback.json"):
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

    path = Path(__file__, "..")

    # Load feedback data from the JSON file
    with open(path.getFilePath(feedback_file), "r", encoding="utf-8") as file:
        tests_feedback = json.load(file)
    passed = True if final_score >= 70 else False
    # Initialize feedback
    feedback = f"# 🧪 Relatório de Avaliação – Autograder HTML - {author}\n\n"
    feedback += f"**Data:** {datetime.now().strftime('%d/%m/%Y %H:%M')}\n\n"
    feedback += f"**Nota Final:** `{format(final_score,'.2f')}/100`\n"
    feedback += f"**Status:** {'✅ Aprovado' if passed else '❌ Reprovado'}\n\n"
    feedback += "---\n"

    # Base Feedback (Requisitos Obrigatórios)
    feedback += "## ✅ Requisitos Obrigatórios (80%)\n"
    if len(base["failed"]) == 0:
        feedback += "- Todos os requisitos básicos foram atendidos. Excelente trabalho!\n"
    else:
        feedback += f"- Foram encontrados `{len(base['failed'])}` problemas nos requisitos obrigatórios. Veja abaixo os testes que falharam:\n"
        for test_name in base["failed"]:
            # Get the feedback from the JSON structure based on pass/fail
            passed_feedback = get_key_value(tests_feedback["base_tests"],test_name)[1]  # Failed feedback
            feedback += f"  - ⚠️ **Falhou no teste**: `{test_name}`\n"
            feedback += f"    - **Melhoria sugerida**: {passed_feedback}\n"

    # Bonus Feedback
    feedback += "\n## ⭐ Itens de Destaque (20%)\n"
    if len(bonus["passed"]) > 0:
        feedback += f"- Você conquistou `{len(bonus['passed'])}` bônus! Excelente trabalho nos detalhes adicionais!\n"
        for passed_test in bonus["passed"]:
            # Get the feedback for passed bonus tests
            passed_feedback = get_key_value(tests_feedback["bonus_tests"],passed_test)[0]  # Failed feedback
            feedback += f"  - 🌟 **Testes bônus passados**: `{passed_test}`\n"
            feedback += f"    - {passed_feedback}\n"
    else:
        feedback += "- Nenhum item bônus foi identificado. Tente adicionar mais estilo e complexidade ao seu código nas próximas tentativas!\n"

    # Penalty Feedback
    feedback += "\n## ❌ Problemas Detectados (Descontos de até -30%)\n"
    if len(penalty["passed"]) > 0 :
        feedback += f"- Foram encontrados `{len(penalty['passed'])}` problemas que acarretam descontos. Veja abaixo os testes penalizados:\n"
        for failed_test in penalty["passed"]:
            # Get the feedback for failed penalty tests
            failed_feedback = get_key_value(tests_feedback["penalty_tests"],failed_test)[0]  # Failed feedback
            feedback += f"  - ⚠️ **Falhou no teste de penalidade**: `{failed_test}`\n"
            feedback += f"    - **Correção sugerida**: {failed_feedback}\n"
    else:
        feedback += "- Nenhuma infração grave foi detectada. Muito bom nesse aspecto!\n"

    feedback += "\n---\n"
    feedback += "Continue praticando e caprichando no código. Cada detalhe conta! 💪\n"

    return feedback