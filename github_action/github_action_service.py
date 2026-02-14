import json
import os

from autograder.autograder import build_pipeline, AutograderPipeline
from github import Github
from github.GithubException import UnknownObjectException
from autograder.models.dataclass.submission import Submission
from github.Repository import Repository
from github.WorkflowRun import WorkflowRun
from github.CheckRun import CheckRun


class GithubActionService:
    """ """

    def __init__(self, github_token, app_token):
        super().__init__()
        self.github_token = github_token
        self.app_token = app_token
        self.repo = self.get_repository(app_token)

    def run_autograder(
        self,
        pipeline: AutograderPipeline,
        user_name: str,
    ):
        """
        Docstring for run_autograder

        :param self: Description
        """
        try:
            submission = Submission(
                username=user_name,
                user_id=self.github_token,
                assignment_id=self.app_token,
                submission_files=self.__get_submission_files(),
            )

            return pipeline.run(submission)
        except Exception as e:
            raise Exception(f"Error running autograder: {e}") from e

    def get_repository(self, app_token):
        """
        Docstring for get_repository

        :param self: Description
        :param app_token: Description
        """
        try:
            repo = os.getenv("GITHUB_REPOSITORY")
            if not repo:
                raise Exception('Not find repo')

            return Github(app_token).get_repo(repo)
        except:
            raise Exception(
                "Failed to get repository. Please check your GitHub token and repository settings."
            )

    def export_results(
        self, final_score: float, include_feedback: bool, feedback: str | None
    ):
        """
        Docstring for export_results

        :param self: Description
        """
        if include_feedback and feedback is not None:
            self.commit_feedback(feedback)
        self.notify_classroom(final_score)

    def notify_classroom(self, final_score: float):
        """
        Docstring for notify_classroom

        :param self: Description
        """
        if final_score < 0 or final_score > 100:
            raise Exception("Invalid final score. It should be between 0 and 100.")

        repo_name = os.getenv("GITHUB_REPOSITORY")
        if not repo_name:
            raise Exception("Repository information is missing.")

        run_id = os.getenv("GITHUB_RUN_ID")
        if not run_id:
            raise Exception("Run ID is missing.")

        g = Github(os.getenv("GITHUB_TOKEN"))
        repo = g.get_repo(repo_name)

        workflow_run = repo.get_workflow_run(int(run_id))
        check_run = self.__find_check_suite(repo, workflow_run)

        text = f"Final Score: {format(final_score, '.2f')}/100"

        check_run.edit(
            name="Autograding",
            output={
                "title": "Autograding Result",
                "summary": text,
                "text": json.dumps(
                    {"totalPoints": format(final_score, ".2f"), "maxPoints": 100}
                ),
                "annotations": [
                    {
                        "path": ".github",
                        "start_line": 1,
                        "end_line": 1,
                        "annotation_level": "notice",
                        "message": text,
                        "title": "Autograding complete",
                    }
                ],
            },
        )

    def __find_check_suite(
        self, repo: Repository, workflow_run: WorkflowRun
    ) -> CheckRun:
        check_suite_url = workflow_run.check_suite_url
        check_suite_id = int(check_suite_url.split("/")[-1])

        check_runs = repo.get_check_suite(check_suite_id)
        check_run = next(
            (run for run in check_runs.get_check_runs() if run.name == "grading"), None
        )
        if not check_run:
            raise Exception("Check run not found.")

        return check_run

    def commit_feedback(self, feedback: str):
        """
        Docstring for commit_feedback

        :param self: Description
        """
        file_path = "relatorio.md"

        try:
            file = self.repo.get_contents(file_path)
            if isinstance(file, list):
                file = file[0]

            self.repo.update_file(
                path=file_path,
                message=f"Atualizando relatório: {file_path}",
                content=feedback,
                sha=file.sha,
            )
        except UnknownObjectException:
            self.repo.create_file(
                path=file_path,
                message=f"Criando relatório: {file_path}",
                content=feedback,
            )

    def __get_submission_files(self):
        """
        Docstring for get_submission_files

        :param self: Description
        """
        base_path = os.getenv("GITHUB_WORKSPACE", ".")
        submission_path = os.path.join(base_path, "submission")
        submission_files_dict = {}

        # take all files in the submission directory and add them to the submission_files_dict
        for root, dirs, files in os.walk(submission_path):
            # Skip .git directory
            if ".git" in dirs:
                dirs.remove(".git")
            if ".github" in dirs:
                dirs.remove(".github")
            for file in files:
                # Full path to the file
                file_path = os.path.join(root, file)

                # Key: Path relative to the starting directory to ensure uniqueness
                relative_path = os.path.relpath(file_path, submission_path)

                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        print("Adding file to submission_files_dict: ", relative_path)
                        # Use the unique relative_path as the key
                        submission_files_dict[relative_path] = f.read()
                except Exception as e:
                    print(f"Could not read file {file_path}: {e}")

        return submission_files_dict

    def autograder_pipeline(
        self, template_preset, include_feedback: bool, feedback_mode
    ):
        """
        Looks inside $GITHUB_WORKSPACE/submission/.github/autograder for the criteria.json, feedback.json and setup.json files.
        """
        base_path = os.getenv("GITHUB_WORKSPACE", ".")
        submission_path = os.path.join(base_path, "submission")
        configuration_path = os.path.join(submission_path, ".github", "autograder")

        return build_pipeline(
            template_name=template_preset,
            grading_criteria=self.__read_path(configuration_path, "criteria.json"),
            feedback_config=self.__read_path(configuration_path, "feedback.json"),
            setup_config=self.__read_path(configuration_path, "setup.json"),
            include_feedback=include_feedback,
            feedback_mode=feedback_mode,
        )

    def __read_path(self, configuration_path: str, file_name: str):
        path = os.path.join(configuration_path, file_name)

        if not os.path.exists(path):
            raise FileNotFoundError(
                f"{file_name} file not found in the autograder configuration directory."
            )

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @classmethod
    def create(
        cls,
        test_framework,
        github_author,
        app_token,
    ):
        """
        Docstring for create

        :param cls: Description
        :param test_framework: Description
        :param github_author: Description
        :param app_token: Description
        """
        response = cls(test_framework, github_author)
        response.get_repository(app_token)
        return response
