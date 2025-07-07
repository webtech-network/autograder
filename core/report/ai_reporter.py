from core.report.base_reporter import BaseReporter
from openai import OpenAI
import os

class AIReporter(BaseReporter):
    def __init__(self,result,token,quota,openai_key=None):
        super().__init__(result,token)
        self.client = OpenAI(api_key=openai_key)
        self.quota = quota
    def generate_feedback(self, student_quota=10):
        candidate_code = """\
            def add(a, b):
                return a + b
            """

        test_results = {
            "base": self.result.base_results,
            "bonus": self.result.bonus_results,
            "penalty": self.result.penalty_results["passed"],
            "score": self.result.final_score
        }


        system_prompt = (

            "Você é um revisor de código especialista. Você acabou de receber a solução de um candidato "
            "para um desafio de código. O desafio é de implementar um servidor em Node.js utilizando o framework Express.js. "
            "O usuário deve implementar um servidor que responda a requisições HTTP GET e POST, "
            "e deve implementar as rotas necessárias para atender aos requisitos do desafio. "
            "Seu trabalho é fornecer um feedback amigável, humano e motivador com base nos erros detectados no código do candidato. "
            "Você deve apontar todos os erros encontrados no código, analisá-los detalhadamente e explicar como o candidato pode corrigi-los para atingir uma nota melhor. "
            "Além disso, você deve fazer uma análise geral do código submetido, destacando pontos positivos e negativos, como nomes de variáveis, estrutura do código, organização, etc. "
            "Seu tom deve ser casual, empático, humano e construtivo. "
            "Você deve retornar respostas formatadas em markdown, isso é obrigatório. "
            "A resposta deve ser apenas em direção ao candidato, sem mencionar o revisor ou o sistema. "
            "Em momento algum você deve mencionar a existência de testes unitários sendo executados por um sistema de avaliação automatizado. "
            "Você deve fornecer o feedback como se fosse um revisor que realmente leu o código do candidato e está fornecendo feedback sobre ele."
        )

        user_prompt = f"""
            Nome do aluno: {self.result.author}
            ### 🧪 Código submetido:

            ```python
            {self.result.submission_file}
            ```

            ### 📊 Resultados dos testes:

            **Testes passados:**
            {test_results['base']['passed']}

            **Testes falhados:**
            {test_results['base']['failed']}

            **Testes bônus passados:**
            {test_results['bonus']['passed']}

            **Penalidades detectadas:**
            {test_results['penalty']}

            ### 📝 Instruções para o feedback:

            - Aponte todos os erros detectados no código do aluno, explicando detalhadamente o que está errado e como ele pode corrigir.
            - Faça uma análise geral do código submetido, destacando pontos positivos e negativos, como nomes de variáveis, estrutura do código, organização, etc.
            - Forneça orientações claras e práticas para o candidato melhorar seu código e atingir uma nota melhor.
            - Seja amigável, humano e motivador em seu tom.
            - Retorne o feedback em uma estrutura bem feita em markdown com elementos de títulos, indentação e listas. Markdown é obrigatório.
            - Não mencione a existência de testes unitários ou sistemas automatizados de avaliação.
            - Mostre que você leu o código do candidato, apontando pequenos detalhes específicos do código.
            - Divulgue a nota final do candidato de forma objetiva antes de sua análise.

            **Nota final:** {test_results['score']}/100
        """

        response = self.client.chat.completions.create(model="gpt-3.5-turbo",
                                                  messages=[
                                                      {"role": "system", "content": system_prompt},
                                                      {"role": "user", "content": user_prompt}
                                                  ],
                                                  temperature=0.7)
        ai_quota = f"Você tem {self.quota} créditos restantes para usar o sistema de feedback AI.\n"
        feedback = ai_quota + response.choices[0].message.content
        return feedback

    @classmethod
    def create(cls, result, token, quota, openai_key=None):
        """Factory method to create an AIReporter instance."""
        response = cls(result, token, quota,openai_key)
        response.get_repository()
        return response

