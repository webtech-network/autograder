# pylint: disable=protected-access

import json
import os
import pytest
from unittest.mock import MagicMock, patch, mock_open

from github.GithubException import UnknownObjectException

from github_action.github_action_service import GithubActionService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(github_token="gh-token", app_token="app-token", repo="owner/repo"):
    """Create a GithubActionService with get_repository mocked out."""
    with patch.dict(os.environ, {"GITHUB_REPOSITORY": repo}), patch(
        "github_action.github_action_service.Github"
    ) as mock_github:
        mock_github.return_value.get_repo.return_value = MagicMock()
        service = GithubActionService(github_token, app_token)
    return service


class TestGetRepository:
    """
    __init__ / get_repository
    """

    def test_returns_repo_when_env_var_set(self):
        """Asserts the repository is returned correctly when GITHUB_REPOSITORY is set in the environment."""
        mock_repo = MagicMock()
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}), patch(
            "github_action.github_action_service.Github"
        ) as mock_github:
            mock_github.return_value.get_repo.return_value = mock_repo
            service = GithubActionService("token", "app-token")

        assert service.repo is mock_repo
        mock_github.return_value.get_repo.assert_called_once_with("owner/repo")

    def test_raises_when_github_repository_missing(self):
        """Asserts an exception is raised when the GITHUB_REPOSITORY environment variable is not set."""
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_REPOSITORY"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(Exception, match="Failed to get repository"):
                GithubActionService("token", "app-token")

    def test_raises_when_github_api_fails(self):
        """Asserts an exception is raised when the GitHub API returns an error while fetching the repository."""
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}), patch(
            "github_action.github_action_service.Github"
        ) as mock_github:
            mock_github.return_value.get_repo.side_effect = RuntimeError("API error")
            with pytest.raises(Exception, match="Failed to get repository"):
                GithubActionService("token", "app-token")

    def test_stores_github_token_and_app_token(self):
        """Asserts that github_token and app_token are correctly stored as instance attributes."""
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}), patch(
            "github_action.github_action_service.Github"
        ):
            service = GithubActionService("my-gh-token", "my-app-token")

        assert service.github_token == "my-gh-token"
        assert service.app_token == "my-app-token"


class TestRunAutograder:
    """
    run_autograder()
    """

    def test_returns_pipeline_result_on_success(self):
        """Asserts the pipeline result is returned when execution completes successfully."""
        service = _make_service()
        mock_pipeline = MagicMock()
        mock_result = MagicMock()
        mock_pipeline.run.return_value = mock_result

        result = service.run_autograder(
            mock_pipeline, "student1", {"file.py": "content"}
        )

        assert result is mock_result
        mock_pipeline.run.assert_called_once()

    def test_submission_built_with_correct_fields(self):
        """Asserts the Submission object is built with the correct username, user_id, assignment_id, and submission_files."""
        service = _make_service(github_token="gh-tok", app_token="app-tok")
        mock_pipeline = MagicMock()
        submission_files = {"main.py": "print('hi')"}

        with patch(
            "github_action.github_action_service.Submission"
        ) as mock_submission_cls:
            service.run_autograder(mock_pipeline, "alice", submission_files)

        mock_submission_cls.assert_called_once_with(
            username="alice",
            user_id="gh-tok",
            assignment_id="app-tok",
            submission_files=submission_files,
        )

    def test_wraps_exception_on_pipeline_failure(self):
        """Asserts that exceptions raised by the pipeline are wrapped in a new exception with an appropriate message."""
        service = _make_service()
        mock_pipeline = MagicMock()
        mock_pipeline.run.side_effect = RuntimeError("pipeline boom")

        with pytest.raises(Exception, match="Error running autograder"):
            service.run_autograder(mock_pipeline, "student1", {})


class TestExportResults:
    """
    export_results()
    """

    def test_calls_commit_and_notify_when_feedback_included(self):
        """Asserts __commit_feedback and __notify_classroom are both called when include_feedback is True and feedback is not None."""
        service = _make_service()
        with patch.object(
            service, "_GithubActionService__commit_feedback"
        ) as mock_commit, patch.object(
            service, "_GithubActionService__notify_classroom"
        ) as mock_notify:
            service.export_results(90.0, include_feedback=True, feedback="Great job!")

        mock_commit.assert_called_once_with("Great job!")
        mock_notify.assert_called_once_with(90.0)

    def test_skips_commit_when_include_feedback_false(self):
        """Asserts __commit_feedback is not called when include_feedback is False, even if feedback is provided."""
        service = _make_service()
        with patch.object(
            service, "_GithubActionService__commit_feedback"
        ) as mock_commit, patch.object(
            service, "_GithubActionService__notify_classroom"
        ) as mock_notify:
            service.export_results(
                75.0, include_feedback=False, feedback="Some feedback"
            )

        mock_commit.assert_not_called()
        mock_notify.assert_called_once_with(75.0)

    def test_skips_commit_when_feedback_is_none(self):
        """Asserts __commit_feedback is not called when feedback is None, even if include_feedback is True."""
        service = _make_service()
        with patch.object(
            service, "_GithubActionService__commit_feedback"
        ) as mock_commit, patch.object(
            service, "_GithubActionService__notify_classroom"
        ) as mock_notify:
            service.export_results(50.0, include_feedback=True, feedback=None)

        mock_commit.assert_not_called()
        mock_notify.assert_called_once_with(50.0)

    def test_skips_commit_when_both_feedback_false_and_none(self):
        """Asserts __commit_feedback is not called when both include_feedback is False and feedback is None."""
        service = _make_service()
        with patch.object(
            service, "_GithubActionService__commit_feedback"
        ) as mock_commit, patch.object(
            service, "_GithubActionService__notify_classroom"
        ) as mock_notify:
            service.export_results(0.0, include_feedback=False, feedback=None)

        mock_commit.assert_not_called()
        mock_notify.assert_called_once_with(0.0)


class TestNotifyClassroom:
    """
    __notify_classroom()
    """

    def _call_notify(self, service, score):
        """Reach the private method directly via name mangling."""
        service._GithubActionService__notify_classroom(score)

    def test_raises_when_score_below_zero(self):
        """Asserts an exception is raised when the given score is below zero."""
        service = _make_service()
        with pytest.raises(Exception, match="Invalid final score"):
            self._call_notify(service, -1.0)

    def test_raises_when_score_above_hundred(self):
        """Asserts an exception is raised when the given score is above 100."""
        service = _make_service()
        with pytest.raises(Exception, match="Invalid final score"):
            self._call_notify(service, 100.1)

    def test_raises_when_github_repository_missing(self):
        """Asserts an exception is raised when GITHUB_REPOSITORY is not set while notifying the classroom."""
        service = _make_service()
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_REPOSITORY"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(Exception, match="Repository information is missing"):
                self._call_notify(service, 80.0)

    def test_raises_when_github_run_id_missing(self):
        """Asserts an exception is raised when GITHUB_RUN_ID is not set in the environment."""
        service = _make_service()
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_RUN_ID"}
        env["GITHUB_REPOSITORY"] = "owner/repo"
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(Exception, match="Run ID is missing"):
                self._call_notify(service, 80.0)

    def test_calls_check_run_edit_on_success(self):
        """Asserts check_run.edit is called with name 'Autograding' and the formatted score in the summary on a successful notification."""
        service = _make_service()
        mock_check_run = MagicMock()

        with patch.dict(
            os.environ,
            {
                "GITHUB_REPOSITORY": "owner/repo",
                "GITHUB_RUN_ID": "123",
                "GITHUB_TOKEN": "token",
            },
        ), patch(
            "github_action.github_action_service.Github"
        ) as mock_github, patch.object(
            service,
            "_GithubActionService__find_check_suite",
            return_value=mock_check_run,
        ):
            mock_github.return_value.get_repo.return_value = MagicMock()
            self._call_notify(service, 85.5)

        mock_check_run.edit.assert_called_once()
        call_kwargs = mock_check_run.edit.call_args[1]
        assert call_kwargs["name"] == "Autograding"
        assert "85.50" in call_kwargs["output"]["summary"]

    def test_score_at_boundary_zero_is_valid(self):
        """Asserts that a score of 0.0 is a valid boundary value and does not raise an exception."""
        service = _make_service()
        mock_check_run = MagicMock()

        with patch.dict(
            os.environ,
            {
                "GITHUB_REPOSITORY": "owner/repo",
                "GITHUB_RUN_ID": "42",
                "GITHUB_TOKEN": "token",
            },
        ), patch("github_action.github_action_service.Github"), patch.object(
            service,
            "_GithubActionService__find_check_suite",
            return_value=mock_check_run,
        ):
            self._call_notify(service, 0.0)  # should not raise

        mock_check_run.edit.assert_called_once()

    def test_score_at_boundary_hundred_is_valid(self):
        """Asserts that a score of 100.0 is a valid boundary value and does not raise an exception."""
        service = _make_service()
        mock_check_run = MagicMock()

        with patch.dict(
            os.environ,
            {
                "GITHUB_REPOSITORY": "owner/repo",
                "GITHUB_RUN_ID": "42",
                "GITHUB_TOKEN": "token",
            },
        ), patch("github_action.github_action_service.Github"), patch.object(
            service,
            "_GithubActionService__find_check_suite",
            return_value=mock_check_run,
        ):
            self._call_notify(service, 100.0)  # should not raise

        mock_check_run.edit.assert_called_once()


class TestFindCheckSuite:
    """
    __find_check_suite
    """

    def _call_find(self, service, repo, workflow_run):
        return service._GithubActionService__find_check_suite(repo, workflow_run)

    def _make_workflow_run(self, check_suite_id=999):
        workflow_run = MagicMock()
        workflow_run.check_suite_url = (
            f"https://api.github.com/repos/owner/repo/check-suites/{check_suite_id}"
        )
        return workflow_run

    def test_returns_check_run_named_grading(self):
        """Asserts the check run named 'grading' is located and returned correctly among the other check runs."""
        service = _make_service()
        mock_repo = MagicMock()
        workflow_run = self._make_workflow_run(check_suite_id=42)

        grading_run = MagicMock()
        grading_run.name = "grading"
        other_run = MagicMock()
        other_run.name = "other"

        mock_check_suite = MagicMock()
        mock_check_suite.get_check_runs.return_value = [other_run, grading_run]
        mock_repo.get_check_suite.return_value = mock_check_suite

        result = self._call_find(service, mock_repo, workflow_run)

        assert result is grading_run
        mock_repo.get_check_suite.assert_called_once_with(42)

    def test_raises_when_grading_check_run_not_found(self):
        """Asserts an exception is raised when no check run named 'grading' is found in the suite."""
        service = _make_service()
        mock_repo = MagicMock()
        workflow_run = self._make_workflow_run(check_suite_id=7)

        other_run = MagicMock()
        other_run.name = "some-other-run"
        mock_check_suite = MagicMock()
        mock_check_suite.get_check_runs.return_value = [other_run]
        mock_repo.get_check_suite.return_value = mock_check_suite

        with pytest.raises(Exception, match="Check run not found"):
            self._call_find(service, mock_repo, workflow_run)

    def test_raises_when_no_check_runs_exist(self):
        """Asserts an exception is raised when the check suite has no check runs at all."""
        service = _make_service()
        mock_repo = MagicMock()
        workflow_run = self._make_workflow_run()

        mock_check_suite = MagicMock()
        mock_check_suite.get_check_runs.return_value = []
        mock_repo.get_check_suite.return_value = mock_check_suite

        with pytest.raises(Exception, match="Check run not found"):
            self._call_find(service, mock_repo, workflow_run)


class TestCommitFeedback:
    """
    __commit_feedback()
    """

    def _call_commit(self, service, feedback):
        service._GithubActionService__commit_feedback(feedback)

    def test_updates_file_when_it_exists(self):
        """Asserts update_file is called with the existing file's SHA when relatorio.md already exists in the repository."""
        service = _make_service()
        mock_file = MagicMock()
        mock_file.sha = "abc123"
        service.repo = MagicMock()
        service.repo.get_contents.return_value = mock_file

        self._call_commit(service, "my feedback")

        service.repo.update_file.assert_called_once_with(
            path="relatorio.md",
            message="Atualizando relatório: relatorio.md",
            content="my feedback",
            sha="abc123",
        )
        service.repo.create_file.assert_not_called()

    def test_creates_file_when_not_found(self):
        """Asserts create_file is called when relatorio.md does not exist in the repository (404)."""
        service = _make_service()
        service.repo = MagicMock()
        service.repo.get_contents.side_effect = UnknownObjectException(
            404, "Not found", {}
        )

        self._call_commit(service, "new feedback")

        service.repo.create_file.assert_called_once_with(
            path="relatorio.md",
            message="Criando relatório: relatorio.md",
            content="new feedback",
        )
        service.repo.update_file.assert_not_called()

    def test_uses_first_item_when_get_contents_returns_list(self):
        """Asserts the SHA of the first element is used when get_contents returns a list of files."""
        service = _make_service()
        mock_file1 = MagicMock()
        mock_file1.sha = "sha-first"
        mock_file2 = MagicMock()
        mock_file2.sha = "sha-second"
        service.repo.get_contents.return_value = [mock_file1, mock_file2]  # type: ignore

        self._call_commit(service, "feedback content")

        service.repo.update_file.assert_called_once_with(  # type: ignore
            path="relatorio.md",
            message="Atualizando relatório: relatorio.md",
            content="feedback content",
            sha="sha-first",
        )


class TestAutograderPipeline:
    """
    autograder_pipeline / __read_path
    """

    def test_builds_pipeline_with_all_configs(self):
        """Asserts build_pipeline is called with all correct parameters when all three configuration files exist."""
        service = _make_service()
        criteria = {"tests": []}
        feedback = {"mode": "default"}
        setup = {"language": "python"}

        def fake_exists(_path):
            return True

        def fake_open_read(path, *args, **kwargs):  # pylint: disable=unused-argument
            mapping = {
                "criteria.json": criteria,
                "feedback.json": feedback,
                "setup.json": setup,
            }
            for key, val in mapping.items():
                if key in path:
                    return mock_open(read_data=json.dumps(val))()
            raise FileNotFoundError(path)

        with patch.dict(os.environ, {"GITHUB_WORKSPACE": "/workspace"}), patch(
            "os.path.exists", side_effect=fake_exists
        ), patch("builtins.open", side_effect=fake_open_read), patch(
            "github_action.github_action_service.build_pipeline"
        ) as mock_build:
            mock_build.return_value = MagicMock()
            service.autograder_pipeline("python", True, "default")

        mock_build.assert_called_once_with(
            template_name="python",
            grading_criteria=criteria,
            feedback_config=feedback,
            setup_config=setup,
            include_feedback=True,
            feedback_mode="default",
        )

    def test_raises_file_not_found_when_criteria_missing(self):
        """Asserts FileNotFoundError is raised with a message indicating criteria.json when the file does not exist."""
        service = _make_service()

        with patch.dict(os.environ, {"GITHUB_WORKSPACE": "/workspace"}), patch(
            "os.path.exists", return_value=False
        ):
            with pytest.raises(FileNotFoundError, match="criteria.json"):
                service.autograder_pipeline("python", False, "default")

    def test_raises_file_not_found_when_feedback_missing(self):
        """Asserts FileNotFoundError is raised with a message indicating feedback.json when the file does not exist."""
        service = _make_service()

        def fake_exists(path):
            return "criteria.json" in path

        with patch.dict(os.environ, {"GITHUB_WORKSPACE": "/workspace"}), patch(
            "os.path.exists", side_effect=fake_exists
        ), patch("builtins.open", mock_open(read_data="{}")):
            with pytest.raises(FileNotFoundError, match="feedback.json"):
                service.autograder_pipeline("python", False, "default")

    def test_raises_file_not_found_when_setup_missing(self):
        """Asserts FileNotFoundError is raised with a message indicating setup.json when the file does not exist."""
        service = _make_service()

        call_count = {"n": 0}

        def fake_exists(path):
            call_count["n"] += 1
            return "setup.json" not in path

        with patch.dict(os.environ, {"GITHUB_WORKSPACE": "/workspace"}), patch(
            "os.path.exists", side_effect=fake_exists
        ), patch("builtins.open", mock_open(read_data="{}")):
            with pytest.raises(FileNotFoundError, match="setup.json"):
                service.autograder_pipeline("python", False, "default")
