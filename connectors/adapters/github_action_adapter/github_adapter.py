import json
import os
import shutil

from connectors.models.assignment_config import AssignmentConfig
from connectors.models.autograder_request import AutograderRequest
from connectors.models.test_files import TestFiles
from connectors.port import Port
from github import Github
from github.GithubException import UnknownObjectException

class GithubAdapter(Port):
    def __init__(self,github_token,app_token):
        super().__init__()
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

    def create_request(self,submission_files,assignment_config, student_name, student_credentials, feedback_mode="default",openai_key=None, redis_url=None, redis_token=None):
        """
        Creates an AutograderRequest object with the provided parameters.
        """
        submission_path = os.getenv("GITHUB_WORKSPACE/submission", ".")
        submission_files_dict = {}

        # take all files in the submission directory and add them to the submission_files_dict
        for root, dirs, files in os.walk(submission_path):
            for file in files:
                # Full path to the file
                file_path = os.path.join(root, file)

                # Key: Path relative to the starting directory to ensure uniqueness
                relative_path = os.path.relpath(file_path, submission_path)

                try:
                    with open(file_path, "r", encoding='utf-8', errors='ignore') as f:
                        # Use the unique relative_path as the key
                        submission_files_dict[relative_path] = f.read()
                except Exception as e:
                    print(f"Could not read file {file_path}: {e}")

        print(f"Creating AutograderRequest with {feedback_mode} feedback mode")
        self.autograder_request = AutograderRequest(
            submission_files_dict,
            assignment_config,
            student_name,
            student_credentials=student_credentials,
            feedback_mode=feedback_mode,
            openai_key=openai_key,
            redis_url=redis_url,
            redis_token=redis_token
        )
        print(f"AutograderRequest created with {self.autograder_request.feedback_mode} feedback mode")
    def create_custom_assignment_config(self,
                                       test_files,
                                       criteria,
                                       feedback,
                                       preset="custom",
                                       ai_feedback=None,
                                       setup=None,
                                       test_framework="pytest"):
        # Look for test_base,test_penalty and test_bonus files in $submission/.github/autograder/tests
        # Look for criteria.json, feedback.json and ai-feedback.json,autograder-setup.json in $submisison/.github/autograder
        submission_path = os.getenv("GITHUB_WORKSPACE/submission", ".")
        files = TestFiles()
        with open(os.path.join(submission_path, ".github", "autograder", "tests", "test_base.py"), "r") as f:
            files.test_base = f.read()
        with open(os.path.join(submission_path, ".github", "autograder", "tests", "test_bonus.py"), "r") as f:
            files.test_bonus = f.read()
        with open(os.path.join(submission_path, ".github", "autograder", "tests", "test_penalty.py"), "r") as f:
            files.test_penalty = f.read()
        # Add other files ({filename: file_content}) to files.other_files
        with open(os.path.join(submission_path, ".github", "autograder", "tests", "other_files.json"), "r") as f:
            other_files = json.load(f)
            for filename, content in other_files.items():
                files.other_files[filename] = content
        # Saves criteria.json
        with open(os.path.join(submission_path, ".github", "autograder", "criteria.json"), "r") as f:
            criteria_content = f.read()
        # Saves feedback.json
        with open(os.path.join(submission_path, ".github", "autograder", "feedback.json"), "r") as f:
            feedback_content = f.read()
        # Saves ai-feedback.json (if present)
        ai_feedback_content = None
        ai_feedback_path = os.path.join(submission_path, ".github", "autograder", "ai-feedback.json")
        if os.path.exists(ai_feedback_path):
            with open(ai_feedback_path, "r") as f:
                ai_feedback_content = f.read()
        # Saves autograder-setup.json (if present)
        setup_content = None
        setup_path = os.path.join(submission_path, ".github", "autograder", "autograder-setup.json")
        if os.path.exists(setup_path):
            with open(setup_path, "r") as f:
                setup_content = f.read()
        return AssignmentConfig.load_custom(files,criteria_content,feedback_content,ai_feedback=ai_feedback_content,setup=setup_content,test_framework=test_framework)





    @classmethod
    def create(cls,test_framework,github_author,feedback_type,github_token,app_token,openai_key=None,redis_url=None,redis_token=None):
        response = cls(test_framework,github_author,feedback_type,github_token,app_token,openai_key,redis_url,redis_token)
        response.get_repository()
        return response