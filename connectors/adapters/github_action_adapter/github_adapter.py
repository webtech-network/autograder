import json
import os
import shutil

from connectors.models.assignment_config import AssignmentConfig
from connectors.models.autograder_request import AutograderRequest
from connectors.port import Port
from github import Github
from github.GithubException import UnknownObjectException

class GithubAdapter(Port):
    def __init__(self,github_token,app_token):
        super().__init__()
        self.github_token = github_token
        self.app_token = app_token
        self.repo = self.get_repository(app_token)

    def get_repository(self,app_token):
        try:
            repos = os.getenv("GITHUB_REPOSITORY")
            g = Github(app_token)
            repo = g.get_repo(repos)
            print("This repo is: ", repo)
            return repo
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
        # If the autograder_request exists and include_feedback is explicitly False,
        # skip committing the relatorio.md file.
        req = getattr(self, 'autograder_request', None)
        if req is not None and not getattr(req, 'include_feedback', False):
            print("Feedback generation disabled (include_feedback=False), skipping commit of relatorio.md.")
            return

        # Safely get feedback content (may be None or autograder_response may not exist)
        new_content = None
        resp = getattr(self, 'autograder_response', None)
        if resp is not None:
            new_content = getattr(resp, 'feedback', None)
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



    def get_submission_files(self):

        base_path = os.getenv("GITHUB_WORKSPACE", ".")
        submission_path = os.path.join(base_path, 'submission')
        submission_files_dict = {}

        # take all files in the submission directory and add them to the submission_files_dict
        for root, dirs, files in os.walk(submission_path):
         # Skip .git directory
         if '.git' in dirs:
             dirs.remove('.git')
         if '.github' in dirs:
             dirs.remove('.github')
         for file in files:
             # Full path to the file
             file_path = os.path.join(root, file)

             # Key: Path relative to the starting directory to ensure uniqueness
             relative_path = os.path.relpath(file_path, submission_path)

             try:
                 with open(file_path, "r", encoding='utf-8', errors='ignore') as f:
                     print("Adding file to submission_files_dict: ", relative_path)
                     # Use the unique relative_path as the key
                     submission_files_dict[relative_path] = f.read()
             except Exception as e:
                 print(f"Could not read file {file_path}: {e}")

        return submission_files_dict

    def create_request(self, submission_files, assignment_config, student_name, student_credentials, feedback_mode="default", openai_key=None, redis_url=None, redis_token=None, include_feedback = False):
        """
        Creates an AutograderRequest object with the provided parameters.
        """
        
        # Set credentials as environment variables
        if openai_key:
            os.environ["OPENAI_API_KEY"] = openai_key
        if redis_url:
            os.environ["REDIS_URL"] = redis_url
        if redis_token:
            os.environ["REDIS_TOKEN"] = redis_token

        
        print("Getting submission files from the repository...")
        submission_files_dict = self.get_submission_files()
        print(submission_files_dict)
        print(f"Creating AutograderRequest with {feedback_mode} feedback mode")
        self.autograder_request = AutograderRequest(
            submission_files=submission_files_dict,
            assignment_config=assignment_config,
            student_name=student_name,
            student_credentials=student_credentials,
            include_feedback=include_feedback,
            feedback_mode=feedback_mode,
        )
        print(f"AutograderRequest created with {self.autograder_request.feedback_mode} feedback mode")

    def create_assigment_config(self,template_preset):
        """
        Looks inside $GITHUB_WORKSPACE/submission/.github/autograder for the criteria.json, feedback.json and setup.json files.
        """
        base_path = os.getenv("GITHUB_WORKSPACE", ".")
        submission_path = os.path.join(base_path, 'submission')
        configuration_path = os.path.join(submission_path, '.github','autograder')

        criteria_path = os.path.join(configuration_path, 'criteria.json')
        if not os.path.exists(criteria_path):
            raise FileNotFoundError("criteria.json file not found in the autograder configuration directory.")
        feedback_path = os.path.join(configuration_path, 'feedback.json')
        if not os.path.exists(feedback_path):
            raise FileNotFoundError("feedback.json file not found in the autograder configuration directory.")
        setup_path = os.path.join(configuration_path, 'setup.json')


        criteria_dict = None
        feedback_dict = None
        setup_dict = None

        with open(criteria_path, 'r', encoding='utf-8') as f:
            criteria_dict = json.load(f)
        print("Criteria loaded successfully.")



        with open(feedback_path, 'r', encoding='utf-8') as f:
            feedback_dict = json.load(f)
        print("Feedback config loaded successfully.")



        with open(setup_path, 'r', encoding='utf-8') as f:
            setup_dict = json.load(f)
        print("Setup config loaded successfully.")

        custom_template_str = None
        if template_preset == "custom":
            custom_template_path = os.path.join(configuration_path, 'template.py')
            if not os.path.exists(custom_template_path):
                raise FileNotFoundError("Custom template file 'template.py' not found in the autograder configuration directory.")
            with open(custom_template_path, 'r', encoding='utf-8') as f:
                custom_template_str = f.read()
            print("Custom template loaded successfully.")

        assignment_config = AssignmentConfig(
            template=template_preset,
            criteria=criteria_dict,
            feedback=feedback_dict,
            setup=setup_dict,
            custom_template_str=custom_template_str,
        )
        return assignment_config


    @classmethod
    def create(cls,test_framework,github_author,feedback_type,github_token,app_token,openai_key=None,redis_url=None,redis_token=None):
        response = cls(test_framework,github_author)
        response.get_repository(app_token)
        return response