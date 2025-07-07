from abc import ABC, abstractmethod
from github import Github
import os
import json

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

    def notify_classroom(self, token):
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



