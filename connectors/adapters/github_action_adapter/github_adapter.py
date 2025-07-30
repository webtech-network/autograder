import json
import os
import shutil

from connectors.port import Port
from github import Github
from github.GithubException import UnknownObjectException

class GithubAdapter(Port):
    def __init__(self,test_framework,github_author,feedback_type,github_token,app_token,openai_key=None,redis_url=None,redis_token=None):
        super().__init__(
            test_framework,
            github_author,
            github_author,
            feedback_type,
            openai_key,
            redis_url,
            redis_token
        )
        self.github_token = github_token
        self.app_token = app_token
        self.repo = None

    def get_repository(self):
        try:
            repos = os.getenv("GITHUB_REPOSITORY")
            g = Github(self.app_token)
            self.repo = g.get_repo(repos)
            print("This repo is: ", self.repo)
        except:
            raise Exception("Failed to get repository. Please check your GitHub token and repository settings.")

    def notify_classroom(self):
        final_score = self.autograder_response.final_score
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

    def commit_feedback(self):
        file_path = "relatorio.md"
        file_sha = None
        commit_message = ""
        new_content = self.autograder_response.feedback
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
    def export_results(self):
        self.commit_feedback()
        self.notify_classroom()

    def export_submission_files(self):
        """
        Copies the student's submission files from the GitHub workspace
        to the autograder's request bucket for processing.
        """
        print("Exporting submission files for grading...")

        # Get the source directory from the GITHUB_WORKSPACE environment variable.
        workspace_path = os.getenv("GITHUB_WORKSPACE")
        if not workspace_path:
            raise Exception(
                "GITHUB_WORKSPACE environment variable not set. This script must be run within a GitHub Action.")

        source_dir = os.path.join(workspace_path, "submission")

        if not os.path.isdir(source_dir):
            print(f"Warning: Submission directory not found at '{source_dir}'. No files to grade.")
            return

        # Determine the project's root directory to correctly locate the destination.
        # This file's path is: connectors/adapters/github_action_adapter/github_adapter.py
        # The project root is three directory levels up.
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
        destination_dir = os.path.join(project_root, "autograder", "request_bucket", "submission")

        # Ensure the destination directory exists. The finish_session() method in the
        # facade should handle cleanup, but we make sure the path is ready here.
        os.makedirs(destination_dir, exist_ok=True)

        print(f"Copying from: {source_dir}")
        print(f"Copying to:   {destination_dir}")

        # Copy each file and directory from the source to the destination.
        for item_name in os.listdir(source_dir):
            source_item = os.path.join(source_dir, item_name)
            destination_item = os.path.join(destination_dir, item_name)

            try:
                if os.path.isdir(source_item):
                    # If a directory with the same name already exists in the destination,
                    # remove it first to ensure a clean copy of the new submission.
                    if os.path.exists(destination_item):
                        shutil.rmtree(destination_item)
                    shutil.copytree(source_item, destination_item)
                    print(f" - Copied directory: {item_name}")
                else:  # It's a file
                    shutil.copy2(source_item, destination_item)  # copy2 preserves file metadata
                    print(f" - Copied file: {item_name}")
            except Exception as e:
                print(f"Error: Failed to copy '{item_name}'. Reason: {e}")
                raise  # Stop execution if a critical file copy fails.

        print("Submission files exported successfully.")
    @classmethod
    def create(cls,test_framework,github_author,feedback_type,github_token,app_token,openai_key=None,redis_url=None,redis_token=None):
        response = cls(test_framework,github_author,feedback_type,github_token,app_token,openai_key,redis_url,redis_token)
        response.get_repository()
        return response