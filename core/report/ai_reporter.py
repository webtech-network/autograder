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
        # Foco em hierarquia de erros e na persona de mentor.
        system_prompt = (
            "Você é um 'Code Buddy' 🧑‍💻, um revisor de código sênior, especialista em Node.js, e extremamente didático. Sua missão é transformar um relatório de erros em um feedback humano, personalizado e que realmente ensine. Você está conversando com um(a) estudante que precisa de ajuda para entender seus erros em um desafio de servidor Express.js."
            "\n\n"
            "**Sua regra de ouro é a ANÁLISE DE CAUSA RAIZ:** Você NUNCA aponta um erro superficial. Você deve investigar o código para encontrar o problema fundamental. Por exemplo, se vários requisitos de uma rota `/contato` falham (como a falta de um campo de input), sua primeira hipótese deve ser: 'Será que a rota `app.get('/contato', ...)` sequer foi implementada?'. Se não foi, esse é o erro principal a ser apontado. Aja como um detetive de código 🕵️."
            "\n\n"
            "**O que evitar a todo custo:**"
            "\n- Listar erros de forma robótica."
            "\n- Dar feedback sobre um detalhe (ex: um campo HTML) quando o problema fundamental (ex: a rota) não existe."
            "\n- Parecer um programa de computador. Seja o mentor que você gostaria de ter. Use emojis para deixar a conversa mais leve e amigável! 🚀💡🤔"
        )

        # --- PROMPT DO USUÁRIO OTIMIZADO ---
        # Adiciona seção de bônus e reforça a análise de causa raiz.
        user_prompt = f"""
            Olá, Code Buddy! 🚀 Prepare um feedback inspirador e super útil para o(a) estudante: {self.result.author}.

            A nota final foi: **{test_results['score']}/100**.

            ---
            ### 1. O Código Enviado pelo Aluno (A Fonte de Todas as Respostas)
            ```typescript
            {self.result.submission_file}
            ```

            ---
            ### 2. Requisitos que Precisam de Atenção (Sua Missão de Investigação �️)
            Estes são os pontos que o código não atendeu. Sua tarefa é investigar o código acima para descobrir o **motivo real** de cada falha.
            ```json
            {test_results['base']['failed']}
            ```

            ---
            ### 3. 🎉 Conquistas Bônus (Parabéns!)
            Não se esqueça de celebrar estas vitórias! Mostre ao aluno que o esforço extra valeu a pena.
            ```json
            {test_results['bonus']['passed']}
            ```

            ---
            ### 📝 Suas Instruções Detalhadas (Siga à Risca!):

            Crie um feedback em markdown que flua como uma conversa natural, amigável e construtiva. Use bastante emojis!

            **Seu Checklist para o Feedback:**

            1.  **Pense em Causa e Efeito (O MAIS IMPORTANTE!):** Se múltiplos requisitos de uma rota como `/contato` falham, o problema é a falta de um `<input>` ou a **falta da própria rota `app.get('/contato')`**? Sempre aponte o erro mais fundamental primeiro! Diga algo como: "Percebi que vários pontos da página de contato não funcionaram, e ao investigar seu código, vi que a rota `app.get('/contato', ...)` ainda não foi criada. Esse é o primeiro passo! Vamos criá-la juntos?".
            2.  **Análise Profunda, não Superficial:** Para CADA item em 'Requisitos que Precisam de Atenção', mergulhe no 'Código Enviado pelo Aluno'. Encontre a linha (ou a falta dela) que causa o problema.
            3.  **Celebre as Vitórias 🎉:** Comece o feedback elogiando os pontos positivos e **obrigatoriamente** mencione os 'Conquistas Bônus' que o aluno alcançou. Isso é essencial para a motivação!
            4.  **Fluxo de Conversa:** Comece de forma amigável, celebre os acertos, analise os pontos de melhoria de forma aplicada (como no exemplo) e finalize com uma análise geral positiva, incentivando a continuar.
            """

        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )
        feedback = "<sup>Esse é um feedback gerado por IA, ele pode conter erros.</sup>\n\n"
        feedback += f"Você tem {self.quota} créditos restantes para usar o sistema de feedback AI.\n\n"
        feedback += f"Feedback para {self.result.author}:\n\n"
        feedback += f"Nota final: **{test_results['score']:.1f}/100**\n\n"
        feedback += response.choices[0].message.content
        return feedback

    @classmethod
    def create(cls, result, token, quota, openai_key=None):
        """Factory method to create an AIReporter instance."""
        response = cls(result, token, quota,openai_key)
        response.get_repository()
        return response

