from abc import ABC, abstractmethod
from github import Github
import os
import json
from github.GithubException import GithubException, UnknownObjectException

class BaseReporter(ABC):
    """Abstract base class for reporting test results."""
    def __init__(self,result,token):
        self.result = result
        self.token = token
        self.repo = None

    def get_repository(self):
        try:
            repos = os.getenv("GITHUB_REPOSITORY")
            g = Github(self.token)
            self.repo = g.get_repo(repos)
            print("This repo is: ", self.repo)
        except:
            raise Exception("Failed to get repository. Please check your GitHub token and repository settings.")

    from github import UnknownObjectException  # Importe a exceção específica

    def overwrite_report_in_repo(self, file_path="relatorio.md", new_content=""):
        """
        Cria ou atualiza um arquivo de relatório no repositório.
        """
        file_sha = None
        commit_message = ""

        # 1. Tente obter o arquivo para ver se ele já existe
        try:
            file = self.repo.get_contents(file_path)
            file_sha = file.sha
            print(f"Arquivo '{file_path}' encontrado. Preparando para atualizar...")
        except UnknownObjectException:
            print(f"Arquivo '{file_path}' não encontrado. Preparando para criar...")
            pass

        # 2. Fora do try/except, decida se cria ou atualiza
        if file_sha:
            commit_message = f"Atualizando relatório: {file_path}"
            self.repo.update_file(path=file_path, message=commit_message, content=new_content, sha=file_sha)
            print("Relatório atualizado com sucesso.")
        else:
            commit_message = f"Criando relatório: {file_path}"
            self.repo.create_file(path=file_path, message=commit_message, content=new_content)
            print("Relatório criado com sucesso.")

    def notify_classroom(self):
        # Check if the final_score is provided and is between 0 and 100
        final_score = self.result.final_score
        if final_score < 0 or final_score > 100:
            print("Invalid final score. It should be between 0 and 100.")
            return

        # Retrieve the GitHub token and repository information from environment variables

        repo_name = os.getenv("GITHUB_REPOSITORY")
        if not repo_name:
            print("Repository information is missing.")
            return

        token = os.getenv("GITHUB_TOKEN")
        # Create the GitHub client using the token
        g = Github(token)
        repo = g.get_repo(repo_name)

        # Get the workflow run ID
        run_id = os.getenv("GITHUB_RUN_ID")
        if not run_id:
            print("Run ID is missing.")
            return

        # Fetch the workflow run
        workflow_run = repo.get_workflow_run(int(run_id))

        # Find the check suite run ID
        check_suite_url = workflow_run.check_suite_url
        check_suite_id = int(check_suite_url.split('/')[-1])

        # Get the check runs for this suite
        check_runs = repo.get_check_suite(check_suite_id)
        check_run = next((run for run in check_runs.get_check_runs() if run.name == "grading"), None)
        if not check_run:
            print("Check run not found.")
            return
        # Create a summary for the final grade
        text = f"Final Score: {format(final_score, '.2f')}/100"

        # Update the check run with the final score
        check_run.edit(
            name="Autograding",
            output={
                "title": "Autograding Result",
                "summary": text,
                "text": json.dumps({"totalPoints": format(final_score, '.2f'), "maxPoints": 100}),
                "annotations": [{
                    "path": ".github",
                    "start_line": 1,
                    "end_line": 1,
                    "annotation_level": "notice",
                    "message": text,
                    "title": "Autograding complete"
                }]
            }
        )

        print(f"Final grade updated: {format(final_score, '.2f')}/100")

    def create_feedback_file(self):
        with open("feedback.md","w",encoding="utf-8") as f:
            f.write(self.generate_feedback())

    @abstractmethod
    def generate_feedback(self):
        """Generate feedback based on the test results."""
        pass

    @classmethod
    def create(cls,result,token):
        response = cls(result,token)
        response.get_repository()
        return response



