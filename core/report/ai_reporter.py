from core.report.base_reporter import BaseReporter
from openai import OpenAI
import os

class AIReporter(BaseReporter):
    def __init__(self,result,token,quota,openai_key=None):
        super().__init__(result,token)
        self.client = OpenAI(api_key=openai_key)
        self.quota = quota

    def generate_feedback(self):
        test_results = {
            "base": self.result.base_results,
            "bonus": self.result.bonus_results,
            "penalty": self.result.penalty_results["passed"],
            "score": self.result.final_score
        }

        # --- PROMPT DO SISTEMA OTIMIZADO ---
        # Foco em ser um tutor que guia o aluno pela correção dos erros.
        system_prompt = (
            "Você é um tutor de programação especialista e amigável. Sua principal missão é ajudar um estudante a entender por que seu código falhou em um desafio e como ele pode corrigi-lo. "
            "O desafio é implementar um servidor Express.js em Node.js. "
            "Sua tarefa mais importante é analisar os 'Testes Falhados' e, com base neles, explicar os erros conceituais no código do aluno. "
            "Seja empático, didático e motivador. Use um tom casual e construtivo. "
            "Formate sua resposta obrigatoriamente em markdown, como se fosse uma conversa com o aluno. "
            "Nunca mencione a existência de um sistema de avaliação automatizado ou 'testes unitários'. Em vez disso, trate os 'testes falhos' como 'pontos que não foram atendidos' ou 'requisitos a serem corrigidos'."
            "O seu feedback deve ser uma análise de código genuína, como se você mesmo tivesse lido e executado o código."
        )

        # --- PROMPT DO USUÁRIO OTIMIZADO ---
        # Estrutura mais clara e instruções diretas para focar nos erros.
        user_prompt = f"""
            Olá! Por favor, prepare um feedback para o(a) estudante: {self.result.author}.

            A nota final foi: **{test_results['score']}/100**.

            ---
            ### 🎯 Requisitos que Precisam de Atenção (Testes Falhados)
            Estes são os pontos mais importantes que não foram atendidos no código. Sua análise deve começar por aqui.
            ```json
            {test_results['base']['failed']}
            ```

            ---
            ### ✅ Requisitos Atendidos (Testes Passados)
            ```json
            {test_results['base']['passed']}
            ```

            ---
            ### 🚀 Código Enviado pelo Aluno
            ```typescript
            {self.result.submission_file}
            ```

            ---
            ### 📝 Instruções para o Feedback:

            1.  **FOCO OBRIGATÓRIO:** Comece sua análise abordando os **'Requisitos que Precisam de Atenção'**. Para cada um deles, explique em detalhes por que o código do aluno não atendeu ao requisito. Mostre o trecho exato do código que está causando o problema e forneça uma sugestão clara de como corrigi-lo. Esta é a parte mais crítica do seu feedback.
            2.  **Análise Geral:** Após cobrir todos os pontos de falha, faça uma análise geral do código. Comente sobre boas práticas, como a organização do código, nomes de variáveis e estrutura. Se houver pontos positivos, mesmo que o código não tenha passado em tudo, elogie-os para motivar.
            3.  **Tom e Formato:** Mantenha um tom amigável e encorajador. Use markdown para estruturar bem o feedback com títulos, listas e blocos de código.
            4.  **Seja um Mentor:** Aja como um revisor sênior que está guiando um júnior, e não como um programa de computador.
            5.  **Estilização:** Use emojis e formatação em markdown para tornar o feedback mais envolvente e fácil de ler. Por exemplo, use ✅ para testes passados, ❌ para testes falhados, etc.
            """

        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",  # Revertido para o modelo original
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7  # Revertido para a temperatura original
        )

        ai_quota = f"Você tem {self.quota} créditos restantes para usar o sistema de feedback AI.\n"
        feedback = ai_quota + response.choices[0].message.content
        return feedback

    @classmethod
    def create(cls, result, token, quota, openai_key=None):
        """Factory method to create an AIReporter instance."""
        response = cls(result, token, quota,openai_key)
        response.get_repository()
        return response

