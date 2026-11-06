"""ENV-04: the Action runs a released, prebuilt image, and a version is published once.

The image itself is built and checked against real Docker in ``tests/images/``.
"""
# pylint: disable=missing-function-docstring
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts import action_image, sandbox_images

ROOT = Path(__file__).resolve().parents[2]
HEAD = "a" * 40
OTHER = "b" * 40


def test_action_pulls_a_versioned_image_and_builds_nothing():
    runs = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))["runs"]
    assert runs["using"] == "docker"
    assert runs["image"].startswith("docker://")  # a Dockerfile path would be built on every job
    reference, version = action_image.pinned()
    assert reference == f"ghcr.io/webtech-network/autograder-action:{version}"
    assert "args" not in runs and "entrypoint" not in runs  # the image's own entrypoint runs


@pytest.mark.parametrize("image", ["Dockerfile.actions", "docker://ghcr.io/webtech-network/autograder-action:latest",
                                   "docker://ghcr.io/webtech-network/autograder-action:main",
                                   "docker://ghcr.io/someone/autograder-action:1.0.0", "docker://python:3.13"])
def test_unreleased_or_floating_images_are_not_a_release(tmp_path, image):
    action = tmp_path / "action.yml"
    action.write_text(yaml.safe_dump({"runs": {"using": "docker", "image": image}}))
    with pytest.raises(ValueError, match="released image"):
        action_image.pinned(action)


class Boundary:
    """The registry (docker CLI) and the remote repository (git CLI): answers, and recorded effects."""

    def __init__(self, *, published=False, tagged=()):
        self.published = published
        self.tagged = tagged
        self.effects = []

    def __call__(self, args, **kwargs):
        if args[:3] == ["docker", "manifest", "inspect"]:
            return subprocess.CompletedProcess(args, 0 if self.published else 1, "",
                                               "" if self.published else "manifest unknown")
        if args[:2] == ["git", "rev-parse"]:
            return subprocess.CompletedProcess(args, 0, HEAD + "\n", "")
        if args[:2] == ["git", "ls-remote"]:
            # A lightweight tag lists one line; an annotated one also lists its peeled commit.
            refs = ("refs/tags/0.6.0", "refs/tags/0.6.0^{}")
            lines = "".join(f"{sha}\t{ref}\n" for sha, ref in zip(self.tagged, refs))
            return subprocess.CompletedProcess(args, 0, lines, "")
        assert kwargs.get("check") is True, args
        self.effects.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")


@pytest.fixture
def action(tmp_path):
    path = tmp_path / "action.yml"
    path.write_text(yaml.safe_dump({"runs": {"image": "docker://ghcr.io/webtech-network/autograder-action:0.6.0"}}))
    return path


def test_release_pushes_the_tested_image_before_tagging_this_commit(monkeypatch, action):
    # The tag is what `uses: ...@<version>` resolves, so it never exists without its image.
    boundary = Boundary()
    monkeypatch.setattr(subprocess, "run", boundary)
    action_image.publish("autograder-action:local", action)
    reference = "ghcr.io/webtech-network/autograder-action:0.6.0"
    assert boundary.effects == [["docker", "tag", "autograder-action:local", reference],
                                ["docker", "push", reference],
                                ["git", "tag", "0.6.0", HEAD], ["git", "push", "origin", "refs/tags/0.6.0"]]


def test_published_version_is_never_overwritten_and_its_commit_is_tagged(monkeypatch, action):
    boundary = Boundary(published=True)
    monkeypatch.setattr(subprocess, "run", boundary)
    action_image.publish("autograder-action:local", action)
    assert boundary.effects == [["git", "tag", "0.6.0", HEAD], ["git", "push", "origin", "refs/tags/0.6.0"]]


def test_published_and_tagged_version_does_nothing(monkeypatch, action):
    boundary = Boundary(published=True, tagged=[HEAD])
    monkeypatch.setattr(subprocess, "run", boundary)
    action_image.publish("autograder-action:local", action)
    assert boundary.effects == []


def test_annotated_tag_is_read_as_the_commit_it_names(monkeypatch, action):
    boundary = Boundary(published=True, tagged=[OTHER, HEAD])  # tag object, then the peeled commit
    monkeypatch.setattr(subprocess, "run", boundary)
    action_image.publish("autograder-action:local", action)
    assert boundary.effects == []


def test_tagged_but_unpublished_commit_gets_its_image(monkeypatch, action):
    boundary = Boundary(tagged=[HEAD])
    monkeypatch.setattr(subprocess, "run", boundary)
    action_image.publish("autograder-action:local", action)
    assert [effect[:2] for effect in boundary.effects] == [["docker", "tag"], ["docker", "push"]]


def test_version_tagged_on_another_commit_stops_the_release(monkeypatch, action):
    boundary = Boundary(tagged=[OTHER])
    monkeypatch.setattr(subprocess, "run", boundary)
    with pytest.raises(RuntimeError, match="already names another commit"):
        action_image.publish("autograder-action:local", action)
    assert boundary.effects == []


class Registry:
    """The registry seam of ``check``: answers ``published`` and records the client configuration it was asked with."""

    def __init__(self, *, public=True, error=None):
        self.public = public
        self.error = error
        self.configs = []

    def __call__(self, reference, env=None):
        config = Path(env["DOCKER_CONFIG"])
        self.configs.append((reference, config.is_dir() and not any(config.iterdir())))
        if self.error:
            raise RuntimeError(self.error)
        return self.public


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


RELEASED_ACTION = {"runs": {"using": "docker", "image": "docker://ghcr.io/webtech-network/autograder-action:0.6.0",
                             "env": {"DEFINITION_PATH": "${{ inputs.definition-path }}"}}}
DOCKERFILE = """FROM python:3.13-slim AS dependencies
COPY pyproject.toml ./
FROM python:3.13-slim
COPY --from=dependencies /opt/venv /opt/venv
COPY engine \\
     engine
"""


def write(clone, files):
    for name, content in files.items():
        (clone / name).parent.mkdir(parents=True, exist_ok=True)
        (clone / name).write_text(content if isinstance(content, str) else yaml.safe_dump(content))
    git(clone, "add", "-A")


@pytest.fixture
def history(tmp_path, monkeypatch):
    """A real clone of a real ``origin``: ``release`` is the commit the version was built from.

    The release commit raises the pin in a real ``action.yml`` next to the image's
    sources: a ``Dockerfile.actions`` that copies ``pyproject.toml`` and ``engine``.
    """
    for key, value in {"GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig"), "GIT_CONFIG_NOSYSTEM": "1",
                       "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}.items():
        monkeypatch.setenv(key, value)
    (tmp_path / "gitconfig").write_text("")
    origin, clone = tmp_path / "origin.git", tmp_path / "clone"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    subprocess.run(["git", "clone", "-q", str(origin), str(clone)], check=True, capture_output=True)
    write(clone, {"Dockerfile.actions": DOCKERFILE, ".dockerignore": "*\n", "pyproject.toml": "[project]\n",
                  "engine/grade.py": "SCORE = 100\n", "README.md": "base\n"})
    git(clone, "commit", "-q", "-m", "base")
    git(clone, "push", "-q", "origin", "HEAD:main")
    git(clone, "switch", "-q", "-c", "release")
    write(clone, {"action.yml": RELEASED_ACTION})
    git(clone, "commit", "-q", "-m", "raise the version")
    monkeypatch.chdir(clone)
    return clone


def tag(clone, *, annotated=False):
    git(clone, "tag", *(["-a", "-m", "0.6.0"] if annotated else []), "0.6.0", "release")
    git(clone, "push", "-q", "origin", "refs/tags/0.6.0")


@pytest.mark.parametrize("merge", ["merge", "fast-forward"])
@pytest.mark.parametrize("annotated", [False, True])
def test_check_passes_for_a_public_image_released_from_this_history(monkeypatch, history, capsys,
                                                                    merge, annotated):
    tag(history, annotated=annotated)
    git(history, "switch", "-q", "main")
    git(history, "merge", "-q", *(["--no-ff", "-m", "merge"] if merge == "merge" else ["--ff-only"]), "release")
    registry = Registry()
    monkeypatch.setattr(action_image, "published", registry)
    action_image.check(history)
    # Asked as a consumer's runner asks: with no credentials, even where the caller is logged in.
    assert registry.configs == [("ghcr.io/webtech-network/autograder-action:0.6.0", True)]
    assert "public" in capsys.readouterr().out


def test_check_refuses_a_pin_that_was_never_released(monkeypatch, history, capsys):
    registry = Registry()
    monkeypatch.setattr(action_image, "published", registry)
    with pytest.raises(SystemExit) as stopped:
        action_image.check(history)
    assert stopped.value.code == 1
    assert "not been released" in capsys.readouterr().err and registry.configs == []


def test_check_refuses_an_image_released_from_history_main_does_not_contain(monkeypatch, history, capsys):
    # A squash merge (or a force-push) leaves the dispatched commit, and so the
    # image's source, out of main: @main would run code that was never merged.
    tag(history)
    git(history, "switch", "-q", "main")
    git(history, "merge", "-q", "--squash", "release")
    git(history, "commit", "-q", "--allow-empty", "-m", "squashed release")
    registry = Registry()
    monkeypatch.setattr(action_image, "published", registry)
    with pytest.raises(SystemExit) as stopped:
        action_image.check(history)
    assert stopped.value.code == 1
    message = capsys.readouterr().err
    assert "not in this commit's history" in message and "merge commit" in message
    assert registry.configs == []


@pytest.mark.parametrize("change", [
    {"action.yml": {"runs": {**RELEASED_ACTION["runs"], "env": {"DEFINITION_FILE": "${{ inputs.definition-path }}"}}}},
    {"engine/grade.py": "SCORE = 0\n"},
    {"pyproject.toml": "[project]\ndependencies = []\n"},
    {"Dockerfile.actions": DOCKERFILE + "RUN true\n"},
    {".dockerignore": "*\n!engine/\n"},
], ids=["interface", "copied-code", "copied-dependencies", "dockerfile", "build-context"])
def test_check_refuses_an_action_that_changed_after_its_release(monkeypatch, history, capsys, change):
    # @main consumers read action.yml from the branch but run the image built at the
    # tag: a change to either after the release, without a new version, would make
    # them disagree (e.g. a renamed runs.env key fed to the old entrypoint).
    tag(history)
    git(history, "switch", "-q", "main")
    git(history, "merge", "-q", "--no-ff", "-m", "merge", "release")
    write(history, change)
    git(history, "commit", "-q", "-m", "change the Action without a release")
    registry = Registry()
    monkeypatch.setattr(action_image, "published", registry)
    with pytest.raises(SystemExit) as stopped:
        action_image.check(history)
    assert stopped.value.code == 1
    message = capsys.readouterr().err
    assert "changed after 0.6.0 was released" in message and next(iter(change)) in message
    assert "Raise the version" in message and registry.configs == []


def test_check_ignores_changes_outside_the_release(monkeypatch, history):
    tag(history)
    git(history, "switch", "-q", "main")
    git(history, "merge", "-q", "--no-ff", "-m", "merge", "release")
    write(history, {"README.md": "docs only\n", "tests/test_engine.py": "pass\n"})
    git(history, "commit", "-q", "-m", "docs and tests")
    monkeypatch.setattr(action_image, "published", Registry())
    action_image.check(history)


def test_released_paths_are_what_the_shipped_image_is_built_from():
    assert action_image.released_paths() == [
        "action.yml", "Dockerfile.actions", ".dockerignore", "pyproject.toml", "uv.lock", "sandbox_config.yml",
        "autograder", "execution_host", "sandbox_manager", "github_action"]


def test_check_refuses_a_missing_or_private_image(monkeypatch, history, capsys):
    # Without credentials GHCR answers "denied" for a private package, which reads as absent.
    tag(history)
    monkeypatch.setattr(action_image, "published", Registry(public=False))
    with pytest.raises(SystemExit) as stopped:
        action_image.check(history)
    assert stopped.value.code == 1
    message = capsys.readouterr().err
    assert "autograder-action:0.6.0" in message and "public" in message and "workflow_dispatch" in message


def test_check_cannot_judge_history_it_does_not_have(monkeypatch, history):
    # A shallow clone lacks the tagged commit: an error, never a pass.
    other = history.parent / "other"
    subprocess.run(["git", "init", "-q", str(other)], check=True)
    git(other, "commit", "-q", "--allow-empty", "-m", "unrelated")
    git(other, "push", "-q", str(history.parent / "origin.git"), "HEAD:refs/tags/0.6.0")
    monkeypatch.setattr(action_image, "published", Registry())
    with pytest.raises(RuntimeError, match="cannot tell whether tag 0.6.0"):
        action_image.check(history)


def test_check_refuses_a_registry_answer_it_cannot_read(monkeypatch, history):
    tag(history)
    monkeypatch.setattr(action_image, "published", Registry(error="cannot tell whether it is published"))
    with pytest.raises(RuntimeError, match="cannot tell"):
        action_image.check(history)


def test_published_asks_the_registry_with_the_given_client_configuration(monkeypatch):
    seen = []
    monkeypatch.setattr(subprocess, "run", lambda args, **kwargs: seen.append(kwargs.get("env")) or
                        subprocess.CompletedProcess(args, 1, "", "denied"))
    assert sandbox_images.published("ghcr.io/x/y:1", env={"DOCKER_CONFIG": "/empty"}) is False
    assert seen == [{"DOCKER_CONFIG": "/empty"}]
