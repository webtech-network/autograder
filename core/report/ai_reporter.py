from core.report.base_reporter import BaseReporter
from openai import OpenAI
import os
from core.redis.upstash_driver import decrement_token_quota
class AIReporter(BaseReporter):
    def __init__(self,result,token):
        super().__init__(result,token)
        self.client = OpenAI(api_key=f"{os.getenv('OPENAI_API_KEY')}")
    def generate_feedback(self):
        candidate_code = """\
            def add(a, b):
                return a + b
            """

        test_results = {
            "base": self.result.base_results,
            "bonus": self.result.bonus_results,
            "penalty": self.result.penalty_results,
            "score": self.result.final_score
        }

        system_prompt = (

            "Você é um revisor de código especialista. Você acabou de receber a solução de um candidato "
            "para um desafio de código. O desafio é de implementar um servidor em Node.js utilizando o framework Express.js. "
            "O usuário deve implementar um servidor que responda a requisições HTTP GET e POST, "
            "Ele deve implementar as rotas necessárias para atender aos requisitos do desafio. "
            " Seu trabalho é fornecer um feedback amigável, humano e motivador com base nos "
            "testes de unidade que passaram e falharam. Você elogiará o que é bom, destacará problemas de forma gentil "
            "e incentivará o candidato a melhorar. Seu tom é casual, empático, humano e construtivo. "
            "Você deve retornar respostas formatadas em markdown, isso é obrigatório. "
            "A resposta deve ser apenas em direção ao candidato, sem mencionar o revisor ou o sistema."
            "Em momento algum você deve mencionar a existência de testes unitários sendo executados por um sistema de avaliação automatizado. "
            "Você deve fornecer o feedback sem citar a presença de teste, mostrando que você é simplesmente um revisor que realmente leu o código do candidato e está fornecendo feedback sobre ele."
        )

        user_prompt = f"""
            Nome do aluno: {self.result.author}
            ### 🧪 Código submetido:

            ```python
            {self.result.submission_file}
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
            Lembre-se de em nenhum momento mencionar a existência de testes unitários sendo executados por um sistema de avaliação automatizado.
            Você deve agir como um revisor que realmente leu o código do candidato e está fornecendo feedback sobre ele.
            Não se esqueça de divulgar a nota final do candidato, que é {self.result.final_score}/100. A nota deve ser apresentada antes de sua análise e de forma objetiva.
            """

        response = self.client.chat.completions.create(model="gpt-3.5-turbo",
                                                  messages=[
                                                      {"role": "system", "content": system_prompt},
                                                      {"role": "user", "content": user_prompt}
                                                  ],
                                                  temperature=0.7)
        feedback = response.choices[0].message.content
        return feedback



