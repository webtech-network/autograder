import json
from datetime import datetime
from openai import OpenAI
import os
from utils.path import Path
client = OpenAI(api_key=f"{os.getenv('OPENAI_API_KEY')}")
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

def generate_ai_md(code,base,bonus,penalty,final_score,author):
    candidate_code = """\
    def add(a, b):
        return a + b
    """

    test_results = {
        "base": base,
        "bonus": bonus,
        "penalty":penalty,
        "score": final_score
    }

    system_prompt = (
        "Você é um revisor de código especialista. Você acabou de receber a solução de um candidato "
        "para um desafio de código. Seu trabalho é fornecer um feedback amigável, humano e motivador com base nos "
        "testes de unidade que passaram e falharam. Você elogiará o que é bom, destacará problemas de forma gentil "
        "e incentivará o candidato a melhorar. Seu tom é casual, empático, humano e construtivo. "
        "Você deve retornar respostas formatadas em markdown, isso é obrigatório. "
        "A resposta deve ser apenas em direção ao candidato, sem mencionar o revisor ou o sistema."
    )

    user_prompt = f"""
    Nome do aluno: {author}
    ### 🧪 Código submetido:

    ```python
    {code}
    ```

    ### 📊 Resultados dos testes:

    **Testes base:**  
    {test_results['base']}

    **Testes bônus:**  
    {test_results['bonus']}

    **Testes de penalidade:**  
    {test_results['penalty']}

    **Pontuação final:** {test_results['score']}/100

    Por favor, forneça um feedback amigável, humano e motivador.
    A resposta deve ser apenas em direção ao candidato, sem mencionar o revisor ou o sistema.
    Forneça toda a resposta em uma estrutura bem feita em markdown com elementos de títulos, indentação e listas.Markdown é obrigatório.
    """

    response = client.chat.completions.create(model="gpt-3.5-turbo",
                                              messages=[
                                                  {"role": "system", "content": system_prompt},
                                                  {"role": "user", "content": user_prompt}
                                              ],
                                              temperature=0.7)
    feedback = response.choices[0].message.content
    return feedback

