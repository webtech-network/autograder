import json
import os

from autograder.autograder import build_pipeline, AutograderPipeline
from autograder.models.dataclass.submission import Submission
from github import Github
from github.GithubException import UnknownObjectException
from github.Repository import Repository
from github.WorkflowRun import WorkflowRun
from github.CheckRun import CheckRun


class GithubActionService:
    """
    Service class to integrate the autograder with GitHub Actions workflows.
    Handles repository access, submission file collection, autograder pipeline execution,
    result exporting, feedback committing, and notification to GitHub Classroom.
    """

    def __init__(self, github_token, app_token):
        """
        Initialize the GithubActionService.

        Args:
            github_token (str): The GitHub token for user authentication.
            app_token (str): The GitHub App token for repository access.
        """
        super().__init__()
        self.github_token = github_token
        self.app_token = app_token
        self.repo = self.get_repository(app_token)

    def run_autograder(
        self, pipeline: AutograderPipeline, user_name: str, submission_files: dict
    ):
        """
        Run the autograder pipeline for a given user submission.

        Args:
            pipeline (AutograderPipeline): The autograder pipeline to execute.
            user_name (str): The username of the submitter.

        Returns:
            The result of the pipeline execution.
        """
        try:
            submission = Submission(
                username=user_name,
                user_id=self.github_token,
                assignment_id=self.app_token,
                submission_files=submission_files,
            )

            return pipeline.run(submission)
        except Exception as e:
            raise Exception(f"Error running autograder: {e}") from e

    def get_repository(self, app_token):
        """
        Retrieve the GitHub repository object using the provided app token.

        Args:
            app_token (str): The GitHub App token.

        Returns:
            Repository: The GitHub repository object.
        """
        try:
            repo = os.getenv("GITHUB_REPOSITORY")
            if not repo:
                raise Exception("Repository not found")

            return Github(app_token).get_repo(repo)
        except:
            raise Exception(
                "Failed to get repository. Please check your GitHub token and repository settings."
            )

    def export_results(
        self, final_score: float, include_feedback: bool, feedback: str | None
    ):
        """
        Export the grading results to GitHub, optionally committing feedback.

        Args:
            final_score (float): The final score to report.
            include_feedback (bool): Whether to include feedback in the report.
            feedback (str | None): The feedback content to commit, if any.
        """
        if include_feedback and feedback is not None:
            self.__commit_feedback(feedback)
        self.__notify_classroom(final_score)

    def __notify_classroom(self, final_score: float):
        """
        Notify GitHub Classroom of the final score by updating the check run.

        Args:
            final_score (float): The final score to report (0-100).
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
        """
        Find the check run named 'grading' in the check suite for the workflow run.

        Args:
            repo (Repository): The GitHub repository object.
            workflow_run (WorkflowRun): The workflow run object.

        Returns:
            CheckRun: The check run object for grading.
        """
        check_suite_url = workflow_run.check_suite_url
        check_suite_id = int(check_suite_url.split("/")[-1])

        check_runs = repo.get_check_suite(check_suite_id)
        check_run = next(
            (run for run in check_runs.get_check_runs() if run.name == "grading"), None
        )
        if not check_run:
            raise Exception("Check run not found.")

        return check_run

    def __commit_feedback(self, feedback: str):
        """
        Commit the feedback as a file (relatorio.md) to the repository.

        Args:
            feedback (str): The feedback content to commit.
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

    def autograder_pipeline(
        self, template_preset: str, include_feedback: bool, feedback_mode: str
    ):
        """
        Build the autograder pipeline using configuration files from the submission.

        Looks inside $GITHUB_WORKSPACE/submission/.github/autograder for the criteria.json, feedback.json and setup.json files.

        Args:
            template_preset (str): The template preset name.
            include_feedback (bool): Whether to include feedback in the pipeline.
            feedback_mode(str): The feedback mode to use.

        Returns:
            AutograderPipeline: The constructed autograder pipeline.
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
        """
        Read and parse a JSON configuration file from the given path.

        Args:
            configuration_path (str): The directory containing the configuration file.
            file_name (str): The name of the configuration file.

        Returns:
            dict: The parsed JSON content.
        Raises:
            FileNotFoundError: If the file does not exist.
        """
        path = os.path.join(configuration_path, file_name)

        if not os.path.exists(path):
            raise FileNotFoundError(
                f"{file_name} file not found in the autograder configuration directory."
            )

        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
