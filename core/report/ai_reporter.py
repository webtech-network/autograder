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
        # Foco em criar uma persona de mentor e proibir a listagem de erros.
        system_prompt = (
            "Você é um 'Code Buddy', um revisor de código sênior, especialista em Node.js, e extremamente didático. Sua missão é transformar um relatório de erros em um feedback humano, personalizado e que realmente ensine. Você está conversando com um(a) estudante que precisa de ajuda para entender seus erros em um desafio de servidor Express.js."
            "\n\n"
            "**Sua regra de ouro:** NUNCA apenas liste os erros. Sua tarefa é **investigar** o código do aluno para encontrar a **causa raiz** de cada 'requisito não atendido'. Aja como um detetive de código."
            "\n\n"
            "**O que evitar a todo custo:**"
            "\n- Listas robóticas de erros."
            "\n- Frases como 'O seu código não está respondendo com...'. Prefira 'Notei que na sua resposta para a rota X, o `Content-Type` não foi definido...'."
            "\n- Parecer um programa de computador. Seja o mentor que você gostaria de ter."
            "\n- Mencionar 'testes' ou 'sistemas de avaliação'."
        )

        # --- PROMPT DO USUÁRIO OTIMIZADO ---
        # Estrutura que força a análise aplicada e dá exemplos do que fazer e não fazer.
        user_prompt = f"""
            Olá, Code Buddy! Prepare um feedback inspirador e super útil para o(a) estudante: {self.result.author}.

            A nota final foi: **{test_results['score']}/100**.

            ---
            ### 1. O Código Enviado pelo Aluno (A Fonte de Todas as Respostas)
            ```typescript
            {self.result.submission_file}
            ```

            ---
            ### 2. Requisitos que Precisam de Atenção (Sua Missão de Investigação)
            Estes são os pontos que o código não atendeu. Sua tarefa é investigar o código acima para explicar o porquê de cada um.
            ```json
            {test_results['base']['failed']}
            ```

            ---
            ### 📝 Suas Instruções Detalhadas (Siga à Risca!):

            Crie um feedback em markdown que flua como uma conversa natural e construtiva.

            **Exemplo do que NÃO FAZER (Feedback Robótico e Inútil):**
            > Route: /contato (GET) - deve conter um campo de input...
            > Você esqueceu de adicionar o campo de input com o atributo "name" como "nome".

            **Exemplo de como FAZER (Feedback Humano, Aplicado e Útil):**
            > "E aí, {self.result.author}! Tudo bem? Dei uma olhada no seu servidor e gostei muito de como você estruturou as rotas, ficou bem organizado!
            >
            > Notei um detalhe na sua rota `/contato` que podemos ajustar para que ela funcione 100%. O desafio pedia um campo para o nome do usuário, e parece que ele não foi adicionado ao formulário.
            >
            > Olhando o seu código, na parte que gera o HTML dessa página, podemos adicionar a seguinte linha dentro da tag `<form>`:
            > ```html
            > <input type="text" name="nome" placeholder="Seu nome">
            > ```
            > Isso vai criar o campo que precisamos! O que acha de tentar esse ajuste?"

            **Seu Checklist para o Feedback:**

            1.  **Análise Profunda, não Superficial:** Para CADA item em 'Requisitos que Precisam de Atenção', mergulhe no 'Código Enviado pelo Aluno'. Encontre a linha (ou a falta dela) que causa o problema.
            2.  **Conecte os Pontos:** Sempre mostre a conexão entre o requisito não atendido e o código do aluno. Seja específico. Não diga "faltou um input". Diga "Vi que no seu arquivo `contato.html` (ou na sua string de resposta), dentro da tag `<form>`, está faltando a tag `<input type="text" name="nome">`."
            3.  **Fluxo de Conversa:** Comece de forma amigável, analise os pontos de melhoria de forma aplicada (como no exemplo) e finalize com uma análise geral positiva, elogiando o que foi feito de bom e incentivando a continuar.
            """

        response = self.client.chat.completions.create(
            model="gpt-3.5-turbo",  # Revertido para o modelo original
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7  # Revertido para a temperatura original
        )

        feedback = f"Você tem {self.quota} créditos restantes para usar o sistema de feedback AI.\n"
        feedback += f"Feedback para {self.result.author}:\n"
        feedback += f"Nota final: **{test_results['score']}/100**\n\n"
        feedback += response.choices[0].message.content
        return feedback

    @classmethod
    def create(cls, result, token, quota, openai_key=None):
        """Factory method to create an AIReporter instance."""
        response = cls(result, token, quota,openai_key)
        response.get_repository()
        return response

