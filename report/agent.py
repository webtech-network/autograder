from openai import OpenAI
import os
client = OpenAI(api_key=f"{os.getenv('OPENAI_API_KEY')}")


candidate_code = """\
def add(a, b):
    return a + b
"""


test_results = {
    "base": {
        "test_add_positive_numbers": "passed",
        "test_add_negative_numbers": "failed"
    },
    "bonus": {
        "test_add_floats": "passed"
    },
    "penalty": {
        "test_add_strings": "passed"
    },
    "score": 65
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
### 🧪 Código submetido:

```python
{candidate_code}
```

### 📊 Resultados dos testes:

**Testes base:**  
{test_results['base']}

**Testes bônus:**  
{test_results['bonus']}

**Testes de penalidade:**  
{test_results['penalty']}

**Pontuação final:** {test_results['score']}%

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

print(response.choices[0].message.content)
with open("report.txt", "a") as file:
    file.write(str(response.usage.total_tokens))