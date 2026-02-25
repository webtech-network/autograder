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


# ---------------------------------------------------------------------------
# __init__ / get_repository
# ---------------------------------------------------------------------------


class TestGetRepository:
    def test_returns_repo_when_env_var_set(self):
        mock_repo = MagicMock()
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}), patch(
            "github_action.github_action_service.Github"
        ) as mock_github:
            mock_github.return_value.get_repo.return_value = mock_repo
            service = GithubActionService("token", "app-token")

        assert service.repo is mock_repo
        mock_github.return_value.get_repo.assert_called_once_with("owner/repo")

    def test_raises_when_github_repository_missing(self):
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_REPOSITORY"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(Exception, match="Failed to get repository"):
                GithubActionService("token", "app-token")

    def test_raises_when_github_api_fails(self):
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}), patch(
            "github_action.github_action_service.Github"
        ) as mock_github:
            mock_github.return_value.get_repo.side_effect = RuntimeError("API error")
            with pytest.raises(Exception, match="Failed to get repository"):
                GithubActionService("token", "app-token")

    def test_stores_github_token_and_app_token(self):
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}), patch(
            "github_action.github_action_service.Github"
        ):
            service = GithubActionService("my-gh-token", "my-app-token")

        assert service.github_token == "my-gh-token"
        assert service.app_token == "my-app-token"


# ---------------------------------------------------------------------------
# run_autograder
# ---------------------------------------------------------------------------


class TestRunAutograder:
    def test_returns_pipeline_result_on_success(self):
        service = _make_service()
        mock_pipeline = MagicMock()
        mock_result = MagicMock()
        mock_pipeline.run.return_value = mock_result

        with patch.object(
            service,
            "_GithubActionService__get_submission_files",
            return_value={"file.py": "content"},
        ):
            result = service.run_autograder(mock_pipeline, "student1")

        assert result is mock_result
        mock_pipeline.run.assert_called_once()

    def test_submission_built_with_correct_fields(self):
        service = _make_service(github_token="gh-tok", app_token="app-tok")
        mock_pipeline = MagicMock()
        submission_files = {"main.py": "print('hi')"}

        with patch.object(
            service,
            "_GithubActionService__get_submission_files",
            return_value=submission_files,
        ), patch(
            "github_action.github_action_service.Submission"
        ) as mock_submission_cls:
            service.run_autograder(mock_pipeline, "alice")

        mock_submission_cls.assert_called_once_with(
            username="alice",
            user_id="gh-tok",
            assignment_id="app-tok",
            submission_files=submission_files,
        )

    def test_wraps_exception_on_pipeline_failure(self):
        service = _make_service()
        mock_pipeline = MagicMock()
        mock_pipeline.run.side_effect = RuntimeError("pipeline boom")

        with patch.object(
            service,
            "_GithubActionService__get_submission_files",
            return_value={},
        ):
            with pytest.raises(Exception, match="Error running autograder"):
                service.run_autograder(mock_pipeline, "student1")


# ---------------------------------------------------------------------------
# export_results
# ---------------------------------------------------------------------------


class TestExportResults:
    def test_calls_commit_and_notify_when_feedback_included(self):
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
        service = _make_service()
        with patch.object(
            service, "_GithubActionService__commit_feedback"
        ) as mock_commit, patch.object(
            service, "_GithubActionService__notify_classroom"
        ) as mock_notify:
            service.export_results(0.0, include_feedback=False, feedback=None)

        mock_commit.assert_not_called()
        mock_notify.assert_called_once_with(0.0)


# ---------------------------------------------------------------------------
# __notify_classroom
# ---------------------------------------------------------------------------


class TestNotifyClassroom:
    def _call_notify(self, service, score):
        """Reach the private method directly via name mangling."""
        service._GithubActionService__notify_classroom(score)

    def test_raises_when_score_below_zero(self):
        service = _make_service()
        with pytest.raises(Exception, match="Invalid final score"):
            self._call_notify(service, -1.0)

    def test_raises_when_score_above_hundred(self):
        service = _make_service()
        with pytest.raises(Exception, match="Invalid final score"):
            self._call_notify(service, 100.1)

    def test_raises_when_github_repository_missing(self):
        service = _make_service()
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_REPOSITORY"}
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(Exception, match="Repository information is missing"):
                self._call_notify(service, 80.0)

    def test_raises_when_github_run_id_missing(self):
        service = _make_service()
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_RUN_ID"}
        env["GITHUB_REPOSITORY"] = "owner/repo"
        with patch.dict(os.environ, env, clear=True):
            with pytest.raises(Exception, match="Run ID is missing"):
                self._call_notify(service, 80.0)

    def test_calls_check_run_edit_on_success(self):
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


# ---------------------------------------------------------------------------
# __find_check_suite
# ---------------------------------------------------------------------------


class TestFindCheckSuite:
    def _call_find(self, service, repo, workflow_run):
        return service._GithubActionService__find_check_suite(repo, workflow_run)

    def _make_workflow_run(self, check_suite_id=999):
        workflow_run = MagicMock()
        workflow_run.check_suite_url = (
            f"https://api.github.com/repos/owner/repo/check-suites/{check_suite_id}"
        )
        return workflow_run

    def test_returns_check_run_named_grading(self):
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
        service = _make_service()
        mock_repo = MagicMock()
        workflow_run = self._make_workflow_run()

        mock_check_suite = MagicMock()
        mock_check_suite.get_check_runs.return_value = []
        mock_repo.get_check_suite.return_value = mock_check_suite

        with pytest.raises(Exception, match="Check run not found"):
            self._call_find(service, mock_repo, workflow_run)


# ---------------------------------------------------------------------------
# __commit_feedback
# ---------------------------------------------------------------------------


class TestCommitFeedback:
    def _call_commit(self, service, feedback):
        service._GithubActionService__commit_feedback(feedback)

    def test_updates_file_when_it_exists(self):
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


# ---------------------------------------------------------------------------
# __get_submission_files
# ---------------------------------------------------------------------------


class TestGetSubmissionFiles:
    def _call_get_files(self, service):
        return service._GithubActionService__get_submission_files()

    def test_collects_regular_files(self):
        service = _make_service()
        submission_path = "/workspace/submission"

        walk_data = [
            (submission_path, ["src"], ["readme.txt"]),
            (os.path.join(submission_path, "src"), [], ["main.py"]),
        ]

        file_contents = {
            os.path.join(submission_path, "readme.txt"): "readme content",
            os.path.join(submission_path, "src", "main.py"): "print('hello')",
        }

        def fake_open(path, *args, **kwargs):
            content = file_contents.get(path, "")
            return mock_open(read_data=content)()

        with patch.dict(os.environ, {"GITHUB_WORKSPACE": "/workspace"}), patch(
            "os.walk", return_value=walk_data
        ), patch("builtins.open", side_effect=fake_open):
            result = self._call_get_files(service)

        assert "readme.txt" in result
        assert os.path.join("src", "main.py") in result

    def test_skips_git_directory(self):
        service = _make_service()
        submission_path = "/workspace/submission"

        # os.walk modifies dirs in-place; simulate the walk without .git subtree
        captured_dirs = []

        def fake_walk(path):
            dirs = [".git", "src"]
            captured_dirs.append(dirs)
            yield submission_path, dirs, ["file.py"]
            # After yield, the service removes ".git" from dirs in-place
            # so os.walk wouldn't recurse into it — we only yield one level

        with patch.dict(os.environ, {"GITHUB_WORKSPACE": "/workspace"}), patch(
            "os.walk", side_effect=fake_walk
        ), patch("builtins.open", mock_open(read_data="content")):
            self._call_get_files(service)

        assert ".git" not in captured_dirs[0]

    def test_skips_github_directory(self):
        service = _make_service()
        submission_path = "/workspace/submission"

        captured_dirs = []

        def fake_walk(path):
            dirs = [".github", "src"]
            captured_dirs.append(dirs)
            yield submission_path, dirs, ["file.py"]

        with patch.dict(os.environ, {"GITHUB_WORKSPACE": "/workspace"}), patch(
            "os.walk", side_effect=fake_walk
        ), patch("builtins.open", mock_open(read_data="content")):
            self._call_get_files(service)

        assert ".github" not in captured_dirs[0]

    def test_continues_on_unreadable_file(self):
        service = _make_service()
        submission_path = "/workspace/submission"

        walk_data = [(submission_path, [], ["bad.py", "good.py"])]

        call_count = {"n": 0}

        def fake_open(path, *args, **kwargs):
            call_count["n"] += 1
            if "bad.py" in path:
                raise OSError("Permission denied")
            return mock_open(read_data="good content")()

        with patch.dict(os.environ, {"GITHUB_WORKSPACE": "/workspace"}), patch(
            "os.walk", return_value=walk_data
        ), patch("builtins.open", side_effect=fake_open):
            result = self._call_get_files(service)

        assert "good.py" in result
        assert "bad.py" not in result

    def test_returns_empty_dict_when_no_files(self):
        service = _make_service()
        with patch.dict(os.environ, {"GITHUB_WORKSPACE": "/workspace"}), patch(
            "os.walk", return_value=[]
        ):
            result = self._call_get_files(service)

        assert result == {}

    def test_uses_dot_as_base_when_workspace_not_set(self):
        service = _make_service()
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_WORKSPACE"}

        with patch.dict(os.environ, env, clear=True), patch(
            "os.walk", return_value=[]
        ) as mock_walk:
            self._call_get_files(service)

        expected_path = os.path.join(".", "submission")
        mock_walk.assert_called_once_with(expected_path)


# ---------------------------------------------------------------------------
# autograder_pipeline / __read_path
# ---------------------------------------------------------------------------


class TestAutograderPipeline:
    def test_builds_pipeline_with_all_configs(self):
        service = _make_service()
        criteria = {"tests": []}
        feedback = {"mode": "default"}
        setup = {"language": "python"}

        def fake_exists(path):
            return True

        def fake_open_read(path, *args, **kwargs):
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
        service = _make_service()

        with patch.dict(os.environ, {"GITHUB_WORKSPACE": "/workspace"}), patch(
            "os.path.exists", return_value=False
        ):
            with pytest.raises(FileNotFoundError, match="criteria.json"):
                service.autograder_pipeline("python", False, "default")

    def test_raises_file_not_found_when_feedback_missing(self):
        service = _make_service()

        def fake_exists(path):
            return "criteria.json" in path

        with patch.dict(os.environ, {"GITHUB_WORKSPACE": "/workspace"}), patch(
            "os.path.exists", side_effect=fake_exists
        ), patch("builtins.open", mock_open(read_data="{}")):
            with pytest.raises(FileNotFoundError, match="feedback.json"):
                service.autograder_pipeline("python", False, "default")

    def test_raises_file_not_found_when_setup_missing(self):
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


# ---------------------------------------------------------------------------
# create (classmethod)
# ---------------------------------------------------------------------------


class TestCreate:
    def test_create_calls_get_repository_with_app_token(self):
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}), patch(
            "github_action.github_action_service.Github"
        ) as mock_github:
            mock_repo = MagicMock()
            mock_github.return_value.get_repo.return_value = mock_repo

            service = GithubActionService.create(
                "fw-token", "author-token", "app-token"
            )

        assert isinstance(service, GithubActionService)
        # get_repository is called once in __init__ (with "author-token") and once in create (with "app-token")
        assert mock_github.return_value.get_repo.call_count == 2

    def test_create_sets_correct_tokens(self):
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": "owner/repo"}), patch(
            "github_action.github_action_service.Github"
        ):
            service = GithubActionService.create(
                "fw-token", "author-token", "app-token"
            )

        assert service.github_token == "fw-token"
        assert service.app_token == "author-token"
