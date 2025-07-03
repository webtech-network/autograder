from abc import ABC, abstractmethod
from github import Github
import os

class BaseReporter(ABC):
    """Abstract base class for reporting test results."""
    def __init__(self,result,repo):
        self.result = result
        self.repo = repo
    def get_repository(self,token):
        try:
            repos = os.getenv("GITHUB_REPOSITORY")
            g = Github(token)
            self.repo = g.get_repo(repos)
        except:
            raise Exception("Failed to get repository. Please check your GitHub token and repository settings.")

    def overwrite_report_in_repo(self, file_path="relatorio.md", new_content=""):
        """
        :param file_path:
        :param new_content:
        :return:
        """

        try:
            file = self.repo.get_contents(file_path)
            file_sha = file.sha
        except:
            # If the file doesn't exist, no sha is retrieved
            file_sha = None

            # Encode the updated content in base64

            # Commit the new content to the repository (either overwrite or create new)
            commit_message = "Criando relatório..."
            if file_sha:
                self.repo.update_file(file_path, commit_message, new_content, file_sha)
            else:
                self.repo.create_file(file_path, commit_message, new_content)

            print(f"Report successfully overwritten in {file_path}")


