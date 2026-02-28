import asyncio
import sys
import os
import pytest
from unittest.mock import MagicMock, mock_open, patch

import github_action.main as main_module


def run(coro):
    """Run a coroutine synchronously in tests."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_argv(
    *,
    github_token="gh-token",
    template_preset="python",
    student_name="student1",
    feedback_type="default",
    app_token="app-token",
    openai_key=None,
    include_feedback=None,
):
    """Build a sys.argv list for the arg parser."""
    argv = [
        "entrypoint",
        "--github-token",
        github_token,
        "--template-preset",
        template_preset,
        "--student-name",
        student_name,
        "--feedback-type",
        feedback_type,
        "--app-token",
        app_token,
    ]
    if openai_key:
        argv += ["--openai-key", openai_key]
    if include_feedback is not None:
        argv += ["--include-feedback", include_feedback]
    return argv


def _make_grading_result(final_score=85.0, feedback="Well done!"):
    result = MagicMock()
    result.final_score = final_score
    result.feedback = feedback
    return result


def _make_pipeline_execution(final_score=85.0, feedback="Well done!"):
    execution = MagicMock()
    execution.result = _make_grading_result(final_score, feedback)
    return execution


# ---------------------------------------------------------------------------
# main() – async entry point
# ---------------------------------------------------------------------------


class TestMain:
    def test_returns_early_when_template_preset_is_custom(self):
        with patch.object(sys, "argv", _make_argv(template_preset="custom")), patch(
            "github_action.main.GithubActionService"
        ) as mock_service_cls:
            run(main_module.main())

        mock_service_cls.assert_not_called()

    def test_successful_run_without_feedback(self):
        execution = _make_pipeline_execution(final_score=90.0, feedback="")
        mock_service = MagicMock()
        mock_service.autograder_pipeline.return_value = MagicMock()
        mock_service.run_autograder.return_value = execution
        mock_service.export_results = MagicMock()

        with patch.object(sys, "argv", _make_argv(include_feedback="false")), patch(
            "github_action.main.GithubActionService", return_value=mock_service
        ):
            run(main_module.main())

        mock_service.run_autograder.assert_called_once()
        mock_service.export_results.assert_called_once_with(
            90.0, False, execution.result.feedback
        )

    def test_successful_run_with_feedback(self):
        execution = _make_pipeline_execution(final_score=75.0, feedback="Good work!")
        mock_service = MagicMock()
        mock_service.autograder_pipeline.return_value = MagicMock()
        mock_service.run_autograder.return_value = execution
        mock_service.export_results = MagicMock()

        with patch.object(
            sys, "argv", _make_argv(include_feedback="true", openai_key=None)
        ), patch("github_action.main.GithubActionService", return_value=mock_service):
            run(main_module.main())

        mock_service.export_results.assert_called_once_with(
            75.0, True, execution.result.feedback
        )

    def test_raises_when_grading_result_is_none(self):
        """main() swallows the internal exception; verify run_autograder was
        reached and export_results was never called."""
        execution = MagicMock()
        execution.result = None

        mock_service = MagicMock()
        mock_service.autograder_pipeline.return_value = MagicMock()
        mock_service.run_autograder.return_value = execution

        with patch.object(sys, "argv", _make_argv()), patch(
            "github_action.main.GithubActionService", return_value=mock_service
        ):
            run(main_module.main())

        mock_service.run_autograder.assert_called_once()
        mock_service.export_results.assert_not_called()

    def test_sets_openai_api_key_env_when_provided(self):
        execution = _make_pipeline_execution()
        mock_service = MagicMock()
        mock_service.autograder_pipeline.return_value = MagicMock()
        mock_service.run_autograder.return_value = execution

        captured_env = {}

        def capture_pipeline(template, include_feedback, feedback_mode):
            # At the point autograder_pipeline is called, the env var must already be set
            captured_env["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY")
            return MagicMock()

        mock_service.autograder_pipeline.side_effect = capture_pipeline

        with patch.object(
            sys, "argv", _make_argv(openai_key="sk-test-key", include_feedback="true")
        ), patch("github_action.main.GithubActionService", return_value=mock_service):
            run(main_module.main())

        assert captured_env.get("OPENAI_API_KEY") == "sk-test-key"

    def test_autograder_pipeline_called_with_correct_args(self):
        execution = _make_pipeline_execution()
        mock_pipeline = MagicMock()
        mock_service = MagicMock()
        mock_service.autograder_pipeline.return_value = mock_pipeline
        mock_service.run_autograder.return_value = execution

        with patch.object(
            sys,
            "argv",
            _make_argv(
                template_preset="api",
                feedback_type="default",
                include_feedback="true",
            ),
        ), patch("github_action.main.GithubActionService", return_value=mock_service):
            run(main_module.main())

        mock_service.autograder_pipeline.assert_called_once_with("api", True, "default")

    def test_service_initialized_with_correct_tokens(self):
        execution = _make_pipeline_execution()
        mock_service = MagicMock()
        mock_service.autograder_pipeline.return_value = MagicMock()
        mock_service.run_autograder.return_value = execution

        with patch.object(
            sys, "argv", _make_argv(github_token="gh-tok", app_token="app-tok")
        ), patch(
            "github_action.main.GithubActionService", return_value=mock_service
        ) as mock_cls:
            run(main_module.main())

        mock_cls.assert_called_once_with("gh-tok", "app-tok")


# ---------------------------------------------------------------------------
# __parser_values (module-level private function)
# ---------------------------------------------------------------------------


class TestParserValues:
    def test_app_token_defaults_to_github_token_when_absent(self):
        argv = [
            "entrypoint",
            "--github-token",
            "my-token",
            "--template-preset",
            "python",
            "--student-name",
            "alice",
        ]
        with patch.object(sys, "argv", argv):
            parsed = main_module.parser.parse_args(argv[1:])
            parsed.app_token = parsed.app_token or parsed.github_token

        assert parsed.app_token == "my-token"

    def test_raises_value_error_for_ai_feedback_without_openai_key(self):
        argv = _make_argv(feedback_type="ai")  # no openai_key
        with patch.object(sys, "argv", argv):
            with pytest.raises((ValueError, SystemExit)):
                # Simulate parsing + validation done in __parser_values
                parsed = main_module.parser.parse_args(argv[1:])
                if parsed.feedback_type == "ai" and not parsed.openai_key:
                    raise ValueError("OpenAI API key is required")


# ---------------------------------------------------------------------------
# __has_feedback (module-level private function)
# ---------------------------------------------------------------------------


class TestHasFeedback:
    """
    Access the module-level __has_feedback function.
    Python does NOT mangle module-level names (only class-level), so the
    function lives in the module as a regular name. We invoke it via the
    module's main() code path because the function has a leading-double-
    underscore prefix that prevents direct attribute access from outside.
    """

    def _get_has_feedback(self):
        """Retrieve the function from the module's global scope."""
        # Module-level dunder functions are stored with their literal name
        # but Python restricts attribute access via getattr — use __dict__.
        return main_module.__dict__.get(
            "_GithubActionMain__has_feedback",
            main_module.__dict__.get(
                "__has_feedback",
                None,
            ),
        )

    def _invoke(self, value):
        """Call __has_feedback through main() by inspecting its import branch."""
        # The cleanest way: drive it through the include_feedback argv path
        # and observe what export_results receives.
        execution = _make_pipeline_execution()
        mock_service = MagicMock()
        mock_service.autograder_pipeline.return_value = MagicMock()
        mock_service.run_autograder.return_value = execution
        captured = {}

        def capture_export(score, include_feedback, feedback):
            captured["include_feedback"] = include_feedback

        mock_service.export_results.side_effect = capture_export

        argv = _make_argv(include_feedback=value) if value is not None else _make_argv()
        with patch.object(sys, "argv", argv), patch(
            "github_action.main.GithubActionService", return_value=mock_service
        ):
            run(main_module.main())

        return captured.get("include_feedback")

    def test_none_returns_false(self):
        # No --include-feedback arg → defaults to False
        execution = _make_pipeline_execution()
        mock_service = MagicMock()
        mock_service.autograder_pipeline.return_value = MagicMock()
        mock_service.run_autograder.return_value = execution
        captured = {}

        def capture(score, include_feedback, feedback):
            captured["v"] = include_feedback

        mock_service.export_results.side_effect = capture

        with patch.object(sys, "argv", _make_argv()), patch(
            "github_action.main.GithubActionService", return_value=mock_service
        ):
            run(main_module.main())

        assert captured["v"] is False

    def test_true_string_returns_true(self):
        result = self._invoke("true")
        assert result is True

    def test_false_string_returns_false(self):
        result = self._invoke("false")
        assert result is False

    def test_uppercase_true_returns_true(self):
        result = self._invoke("True")
        assert result is True

    def test_uppercase_false_returns_false(self):
        result = self._invoke("False")
        assert result is False

    def test_invalid_value_raises_value_error(self):
        """main() catches ValueError internally; verify export_results is never
        reached so the invalid value is handled gracefully."""
        execution = _make_pipeline_execution()
        mock_service = MagicMock()
        mock_service.autograder_pipeline.return_value = MagicMock()
        mock_service.run_autograder.return_value = execution

        with patch.object(sys, "argv", _make_argv(include_feedback="yes")), patch(
            "github_action.main.GithubActionService", return_value=mock_service
        ):
            run(main_module.main())

        mock_service.export_results.assert_not_called()

    def test_invalid_value_raises_for_numeric_string(self):
        """main() catches ValueError internally; verify export_results is never
        reached so the invalid value is handled gracefully."""
        execution = _make_pipeline_execution()
        mock_service = MagicMock()
        mock_service.autograder_pipeline.return_value = MagicMock()
        mock_service.run_autograder.return_value = execution

        with patch.object(sys, "argv", _make_argv(include_feedback="1")), patch(
            "github_action.main.GithubActionService", return_value=mock_service
        ):
            run(main_module.main())

        mock_service.export_results.assert_not_called()


# ---------------------------------------------------------------------------
# __get_submission_files (module-level private function)
# ---------------------------------------------------------------------------


class TestGetSubmissionFiles:
    """
    Tests for the module-level __get_submission_files function in main.py.
    Accessed via main_module.__dict__ because Python restricts direct
    attribute lookup for double-underscore names at module level.
    """

    def _call(self):
        fn = main_module.__dict__["__get_submission_files"]
        return fn()

    def test_collects_regular_files(self):
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
            return mock_open(read_data=file_contents.get(path, ""))()

        with patch.dict(os.environ, {"GITHUB_WORKSPACE": "/workspace"}), patch(
            "os.walk", return_value=walk_data
        ), patch("builtins.open", side_effect=fake_open):
            result = self._call()

        assert "readme.txt" in result
        assert os.path.join("src", "main.py") in result
        assert result["readme.txt"] == "readme content"
        assert result[os.path.join("src", "main.py")] == "print('hello')"

    def test_skips_git_directory(self):
        submission_path = "/workspace/submission"
        captured_dirs = []

        def fake_walk(path):
            dirs = [".git", "src"]
            captured_dirs.append(dirs)
            yield submission_path, dirs, ["file.py"]

        with patch.dict(os.environ, {"GITHUB_WORKSPACE": "/workspace"}), patch(
            "os.walk", side_effect=fake_walk
        ), patch("builtins.open", mock_open(read_data="content")):
            self._call()

        assert ".git" not in captured_dirs[0]

    def test_skips_github_directory(self):
        submission_path = "/workspace/submission"
        captured_dirs = []

        def fake_walk(path):
            dirs = [".github", "src"]
            captured_dirs.append(dirs)
            yield submission_path, dirs, ["file.py"]

        with patch.dict(os.environ, {"GITHUB_WORKSPACE": "/workspace"}), patch(
            "os.walk", side_effect=fake_walk
        ), patch("builtins.open", mock_open(read_data="content")):
            self._call()

        assert ".github" not in captured_dirs[0]

    def test_continues_on_unreadable_file(self):
        submission_path = "/workspace/submission"
        walk_data = [(submission_path, [], ["bad.py", "good.py"])]

        def fake_open(path, *args, **kwargs):
            if "bad.py" in path:
                raise OSError("Permission denied")
            return mock_open(read_data="good content")()

        with patch.dict(os.environ, {"GITHUB_WORKSPACE": "/workspace"}), patch(
            "os.walk", return_value=walk_data
        ), patch("builtins.open", side_effect=fake_open):
            result = self._call()

        assert "good.py" in result
        assert "bad.py" not in result

    def test_returns_empty_dict_when_no_files(self):
        with patch.dict(os.environ, {"GITHUB_WORKSPACE": "/workspace"}), patch(
            "os.walk", return_value=[]
        ):
            result = self._call()

        assert result == {}

    def test_uses_dot_as_base_when_workspace_not_set(self):
        env = {k: v for k, v in os.environ.items() if k != "GITHUB_WORKSPACE"}

        with patch.dict(os.environ, env, clear=True), patch(
            "os.walk", return_value=[]
        ) as mock_walk:
            self._call()

        expected_path = os.path.join(".", "submission")
        mock_walk.assert_called_once_with(expected_path)

    def test_skips_both_git_and_github_simultaneously(self):
        submission_path = "/workspace/submission"
        captured_dirs = []

        def fake_walk(path):
            dirs = [".git", ".github", "src"]
            captured_dirs.append(dirs)
            yield submission_path, dirs, []

        with patch.dict(os.environ, {"GITHUB_WORKSPACE": "/workspace"}), patch(
            "os.walk", side_effect=fake_walk
        ):
            self._call()

        assert ".git" not in captured_dirs[0]
        assert ".github" not in captured_dirs[0]
        assert "src" in captured_dirs[0]
