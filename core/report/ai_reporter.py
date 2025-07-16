from core.report.base_reporter import BaseReporter
from openai import OpenAI
from core.config_processing.ai_config import AiConfig
import os





class AIReporter(BaseReporter):
    def __init__(self, result, token, quota, openai_key=None,config=None):
        super().__init__(result, token)
        self.client = OpenAI(api_key=openai_key)
        self.quota = quota
        self.config = config if config else AiConfig.parse_config()

    def _prepare_test_results_str(self):
        results = f"Testes base que falharam:{self.result.base_results['failed']}\n\n"
        results += f"Testes bonus que passaram:{self.result.bonus_results['passed']}\n\n"
        results += f"Testes bonus que falharam:{self.result.bonus_results['failed']}\n\n"
        results += f"Penalidades detectadas:{self.result.penalty_results['passed']}\n\n"
        return results
    def get_system_prompt(self):
        return self.config.system_prompt

    def _assemble_user_prompt(self):
        """Assembles the final user prompt by injecting dynamic data into the template."""

        # 1. Get all the dynamic parts
        test_results_str = self._prepare_test_results_str()
        files_str = self.get_files()
        resources_str = self._prepare_learning_resources_str()

        # Extract author and final_score directly
        author_name = self.result.author
        final_score_value = self.result.final_score

        # 2. Get the template
        prompt_template = self.config.user_prompt

        # 3. Inject data into the template
        return prompt_template.format(
            author=author_name,
            final_score=final_score_value,
            test_results=test_results_str,
            file_contents=files_str,
            learning_resources=resources_str
        )

    def get_files(self):
        """
        Reads files listed in the config from the submission directory
        and formats them into a single string for the AI prompt.
        """
        base_path = os.getenv("GITHUB_WORKSPACE", ".")
        submission_dir = os.path.join(base_path, 'submission')
        formatted_files_content = []
        for filename in self.config.files:
            file_path = os.path.join(submission_dir, filename)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    formatted_files_content.append(f"# ARQUIVO: {filename}\n```\n{content}\n```")
            except FileNotFoundError:
                formatted_files_content.append(f"# ARQUIVO: {filename}\n---\n**O ARQUIVO NÃO EXISTE NO REPOSITORIO DO ALUNO!.**\n---")
        return "\n\n".join(formatted_files_content)

    def _prepare_learning_resources_str(self):
        """Prepares a formatted string of learning resources."""
        if not self.config.learning_resources:
            return "Essa atividade não possui recursos de aprendizado adicionais."

        resource_list = []
        for resource in self.config.learning_resources:
            resource_list.append(f"- {resource.subject}: " + ", ".join(
                f"{res['url']} ({res['description']})" for res in resource.resources))

        return "\n".join(resource_list) if resource_list else "Essa atividade não possui recursos de aprendizado adicionais."

    def generate_feedback(self):
        """Generates feedback using the OpenAI API based on the assembled prompt."""

        system_prompt = self.config.system_prompt
        final_user_prompt = self._assemble_user_prompt()

        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": final_user_prompt}
            ],
            temperature=0.5  # Lowered for more deterministic feedback
        )

        # Now, format the final report
        feedback = "<sup>Esse é um feedback gerado por IA, ele pode conter erros.</sup>\n\n"
        feedback += f"Você tem {self.quota} créditos restantes para usar o sistema de feedback AI.\n\n"
        feedback += f"# Feedback para {self.result.author}:\n\n"
        feedback += f"Nota final: **{self.result.final_score:.1f}/100**\n\n"
        feedback += response.choices[0].message.content
        feedback += "\n\n> Caso queira tirar uma dúvida específica, entre em contato com o Chapter no nosso (discord)[https://discord.gg/gTUbnPgj].\n\n"
        feedback += "\n\n---\n"
        feedback += "<sup>Made By the Autograder Team.</sup><br>&nbsp;&nbsp;&nbsp;&nbsp;<sup><sup>- [Arthur Carvalho](https://github.com/ArthuCRodrigues)</sup></sup><br>&nbsp;&nbsp;&nbsp;&nbsp;<sup><sup>- [Arthur Drumond](https://github.com/drumondpucminas)</sup></sup><br>&nbsp;&nbsp;&nbsp;&nbsp;<sup><sup>- [Gabriel Resende](https://github.com/gnvr29)</sup></sup>"
        return feedback

    @classmethod
    def create(cls, result, token, quota, openai_key=None):
        """Factory method to create an AIReporter instance."""
        response = cls(result, token, quota, openai_key)
        response.get_repository()
        return response