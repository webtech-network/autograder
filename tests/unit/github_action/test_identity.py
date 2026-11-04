"""INT-02: submitter, actor and producer stay separate; publication trust is explicit."""
import json
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from github_action import main
from github_action.identity import (
    TrustError, check_publication_trust, evaluated_commit, resolve_identity, run_provenance,
)

ACTIONS = {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted"}


# --- identity ---------------------------------------------------------------------------


def test_explicit_submitter_wins_over_actor_and_repository():
    env = {"GITHUB_ACTOR": "bob", "GITHUB_TRIGGERING_ACTOR": "bob", "GITHUB_REPOSITORY_ID": "77"}
    identity = resolve_identity("prisma:student:alice", "Alice", env)
    assert (identity.submitter_id, identity.submitter_name, identity.source) == ("prisma:student:alice", "Alice", "input")


def test_name_defaults_to_the_id():
    assert resolve_identity("s-1", None, {}).submitter_name == "s-1"


def test_repository_fallback_never_uses_the_actor():
    env = {"GITHUB_ACTOR": "instructor-bob", "GITHUB_REPOSITORY_ID": "123456",
           "GITHUB_REPOSITORY": "classroom/assignment-alice"}
    identity = resolve_identity(None, None, env)
    assert identity.submitter_id == "github-repository:123456"
    assert identity.submitter_name == "classroom/assignment-alice"
    assert identity.source == "repository"
    assert "bob" not in identity.submitter_id + identity.submitter_name


def test_local_fallback():
    assert resolve_identity("", "  ", {}).submitter_id == "local"


@pytest.mark.parametrize("value", ["has space", "x" * 256, "tab\tid"])
def test_invalid_submitter_ids_fail_clearly(value):
    with pytest.raises(ValueError, match="submitter-id"):
        resolve_identity(value, None, {})


def test_rerun_by_someone_else_preserves_owner_and_records_attempt(tmp_path):
    attempt_1 = {"GITHUB_ACTOR": "alice", "GITHUB_TRIGGERING_ACTOR": "alice", "GITHUB_RUN_ID": "900",
                 "GITHUB_RUN_ATTEMPT": "1", "GITHUB_REPOSITORY_ID": "5"}
    attempt_2 = attempt_1 | {"GITHUB_TRIGGERING_ACTOR": "instructor-bob", "GITHUB_RUN_ATTEMPT": "2"}
    owners = {resolve_identity("prisma-alice", None, env).submitter_id for env in (attempt_1, attempt_2)}
    assert owners == {"prisma-alice"}
    first, second = run_provenance(tmp_path, attempt_1), run_provenance(tmp_path, attempt_2)
    assert (first.run_id, first.run_attempt) == ("900", "1")
    assert (second.run_id, second.run_attempt, second.triggering_actor) == ("900", "2", "instructor-bob")


# --- evaluated commit -------------------------------------------------------------------


def git(root, *args):
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "t",
                        "GIT_COMMITTER_EMAIL": "t@x", "HOME": str(root), "PATH": "/usr/bin:/bin"})


@pytest.fixture
def repository(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "src").mkdir()
    (tmp_path / "src/main.py").write_text("print(1)\n")
    (tmp_path / "README.md").write_text("readme\n")
    (tmp_path / ".gitignore").write_text("*.log\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "init")
    head = subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    return tmp_path, head


def test_clean_checkout_identifies_the_evaluated_commit(repository):
    root, head = repository
    assert evaluated_commit(root) == (head, True)
    assert evaluated_commit(root / "src") == (head, True)


@pytest.mark.parametrize("change", ["modified", "untracked", "ignored"])
def test_local_changes_mean_files_are_not_exactly_the_commit(repository, change):
    root, head = repository
    if change == "modified":
        (root / "src/main.py").write_text("print(2)\n")
    elif change == "untracked":
        (root / "src/extra.py").write_text("x = 1\n")
    else:
        (root / "src/debug.log").write_text("graded but ignored by git\n")
    assert evaluated_commit(root) == (head, False)


def test_changes_outside_the_submission_root_do_not_matter(repository):
    root, head = repository
    (root / "README.md").write_text("changed\n")
    assert evaluated_commit(root / "src") == (head, True)


def test_non_repository_has_no_commit(tmp_path):
    assert evaluated_commit(tmp_path) == (None, None)


def test_event_sha_and_evaluated_commit_are_separate(repository):
    root, head = repository
    provenance = run_provenance(root, {"GITHUB_SHA": "f" * 40})
    assert provenance.event_sha == "f" * 40 and provenance.evaluated_commit == head


# --- trust table ------------------------------------------------------------------------


def pull_request_event(tmp_path, head, base="org/repo"):
    path = tmp_path / "event.json"
    path.write_text(json.dumps({"pull_request": {"head": {"repo": {"full_name": head} if head else None},
                                                 "base": {"repo": {"full_name": base}}}}))
    return str(path)


@pytest.mark.parametrize("event", ["push", "workflow_dispatch", "repository_dispatch", "schedule"])
def test_trusted_events_on_hosted_runners_may_publish(event):
    check_publication_trust(ACTIONS | {"GITHUB_EVENT_NAME": event})


def test_same_repository_pull_request_may_publish(tmp_path):
    check_publication_trust(ACTIONS | {"GITHUB_EVENT_NAME": "pull_request",
                                       "GITHUB_EVENT_PATH": pull_request_event(tmp_path, "org/repo")})


@pytest.mark.parametrize("head", ["fork/repo", None])
def test_fork_pull_requests_cannot_publish(tmp_path, head):
    with pytest.raises(TrustError, match="fork"):
        check_publication_trust(ACTIONS | {"GITHUB_EVENT_NAME": "pull_request",
                                           "GITHUB_EVENT_PATH": pull_request_event(tmp_path, head)})


def test_unreadable_pull_request_payload_fails_closed():
    with pytest.raises(TrustError):
        check_publication_trust(ACTIONS | {"GITHUB_EVENT_NAME": "pull_request", "GITHUB_EVENT_PATH": "/missing"})


@pytest.mark.parametrize("event,reason", [("pull_request_target", "forks"), ("workflow_run", "untrusted"),
                                          ("issue_comment", "Supported events"), ("", "unknown")])
def test_unsupported_events_fail_clearly(event, reason):
    with pytest.raises(TrustError, match=reason):
        check_publication_trust(ACTIONS | {"GITHUB_EVENT_NAME": event})


@pytest.mark.parametrize("runner", ["self-hosted", None])
def test_self_hosted_or_unknown_runner_requires_explicit_trust(runner):
    env = {"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "push"}
    if runner:
        env["RUNNER_ENVIRONMENT"] = runner
    with pytest.raises(TrustError, match="self-hosted"):
        check_publication_trust(env)
    check_publication_trust(env, trusted_self_hosted_runner=True)


def test_trusted_self_hosted_flag_does_not_bypass_unsafe_events():
    with pytest.raises(TrustError):
        check_publication_trust({"GITHUB_ACTIONS": "true", "GITHUB_EVENT_NAME": "pull_request_target",
                                 "RUNNER_ENVIRONMENT": "self-hosted"}, trusted_self_hosted_runner=True)


def test_outside_github_actions_the_operator_is_trusted():
    check_publication_trust({"GITHUB_EVENT_NAME": "pull_request_target"})


# --- CLI wiring -------------------------------------------------------------------------


def test_removed_student_name_fails_with_migration_guidance():
    args = main.parser.parse_args(["--student-name", "alice"])
    with pytest.raises(ValueError, match="submitter-id"):
        main.run(args)


def test_untrusted_publication_fails_before_grading(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request_target")
    monkeypatch.setenv("RUNNER_ENVIRONMENT", "github-hosted")
    args = main.parser.parse_args(["--upload-to-cloud", "true", "--grading-config-id", "7",
                                   "--autograder-cloud-url", "https://cloud.invalid",
                                   "--autograder-cloud-token", "secret"])
    with patch.object(main, "GithubActionService") as service:
        with pytest.raises(TrustError):
            main.run(args)
    service.assert_not_called()
    with patch.object(main, "GithubActionService"), pytest.raises(SystemExit):
        main.main(["--upload-to-cloud", "true", "--grading-config-id", "7", "--autograder-cloud-url",
                   "https://cloud.invalid", "--autograder-cloud-token", "secret"])


def test_retry_delivery_is_also_publication(monkeypatch, tmp_path):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "workflow_run")
    args = main.parser.parse_args(["--retry-delivery-path", "x.json", "--autograder-cloud-url",
                                   "https://cloud.invalid", "--autograder-cloud-token", "secret"])
    with patch.object(main, "CloudClient") as client, pytest.raises(TrustError):
        main.run(args)
    client.assert_not_called()


def test_grading_without_publication_is_not_trust_gated(monkeypatch):
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request_target")
    service = MagicMock()
    service.run_autograder.return_value.model_dump.return_value = {"status": "completed"}
    service.delivery_payload.return_value = None
    with patch.object(main, "GithubActionService", return_value=service), \
            patch.object(main, "collect_files", return_value={}), \
            patch.object(main, "retain_outcome", return_value=MagicMock()), patch.object(main, "logger"):
        main.run(main.parser.parse_args([]))
    service.run_autograder.assert_called_once()


@pytest.mark.parametrize("revision", ["0", "-1"])
def test_revision_must_be_positive(revision):
    with pytest.raises(ValueError, match="revision"):
        main.run(main.parser.parse_args(["--grading-config-revision", revision]))


def test_action_outputs_and_ungraded_directories_do_not_dirty_the_commit(repository):
    root, head = repository
    (root / ".autograder").mkdir()
    (root / ".autograder/outcome.json").write_text("{}")
    (root / "src/.autograder").mkdir()
    (root / "src/.autograder/x").write_text("x")
    (root / ".github").mkdir()
    (root / ".github/new.yml").write_text("x")
    assert evaluated_commit(root) == (head, True)
