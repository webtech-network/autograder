"""ENV-07: main publishes the images it verified, and ``@main`` runs the Action image main publishes.

The git side is real (a clone of a real bare ``origin``); the registry is the
docker CLI, whose answers are scripted and whose effects are recorded. The
images themselves are built and checked against real Docker in ``tests/images/``.
"""
# pylint: disable=missing-function-docstring
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts import publish_images, sandbox_images

ROOT = Path(__file__).resolve().parents[2]
REAL_RUN = subprocess.run
RUNTIMES = [image.ref for image in sandbox_images.catalog()]


def test_action_runs_the_image_main_publishes_and_builds_nothing():
    runs = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))["runs"]
    assert runs["using"] == "docker"
    # A Dockerfile path would be built on every consumer job; a version tag would
    # name an image nothing publishes before 1.0.0.
    assert runs["image"] == "docker://" + publish_images.reference("action", publish_images.CHANNEL)
    assert runs["image"] == "docker://ghcr.io/webtech-network/autograder-action:main"
    assert "args" not in runs and "entrypoint" not in runs  # the image's own entrypoint runs


def test_published_images_are_the_three_built_by_make_images():
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    for service in publish_images.SERVICES:
        assert f"$(IMAGE_PREFIX)-{service}:$(IMAGE_TAG)" in makefile
    assert publish_images.SERVICES[-1] == "action"  # the image @main runs moves last


class Registry:
    """The docker CLI: what the registry holds, per client configuration, and what was pushed."""

    def __init__(self, *, present=(), public=True, lose=()):
        self.present = set(present)
        self.public = public
        self.lose = set(lose)  # pushes the registry acknowledges but does not serve
        self.effects = []

    def __call__(self, args, **kwargs):
        if args[0] == "git":
            return REAL_RUN(args, **kwargs)
        if args[:3] == ["docker", "manifest", "inspect"]:
            env = kwargs.get("env")
            anonymous = env is not None and "DOCKER_CONFIG" in env
            ref = args[3]
            if ref in self.present and (self.public or not anonymous):
                return subprocess.CompletedProcess(args, 0, "{}", "")
            # GHCR's real answers: a package that does not exist yet is "denied"; an
            # existing private package is "unauthorized" to an anonymous client.
            url = f"https://ghcr.io/v2/{ref.split('/', 1)[1].replace(':', '/manifests/')}"
            answer = f'Get "{url}": unauthorized' if ref in self.present else "denied"
            return subprocess.CompletedProcess(args, 1, "", answer)
        assert kwargs.get("check") is True, args
        self.effects.append(args)
        if args[:2] == ["docker", "push"] and args[2] not in self.lose:
            self.present.add(args[2])
        return subprocess.CompletedProcess(args, 0, "", "")

    def pushed(self):
        return [args[2] for args in self.effects if args[:2] == ["docker", "push"]]


def git(cwd, *args):
    return REAL_RUN(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def checkout(tmp_path, monkeypatch):
    """A real clone of a real ``origin``, at the head of ``main``, as the publish job checks it out."""
    for key, value in {"GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig"), "GIT_CONFIG_NOSYSTEM": "1",
                       "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}.items():
        monkeypatch.setenv(key, value)
    (tmp_path / "gitconfig").write_text("")
    origin, clone = tmp_path / "origin.git", tmp_path / "clone"
    REAL_RUN(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    REAL_RUN(["git", "clone", "-q", str(origin), str(clone)], check=True, capture_output=True)
    git(clone, "commit", "-q", "--allow-empty", "-m", "verified")
    git(clone, "push", "-q", "origin", "HEAD:main")
    return clone


def services(commit, tags=None):
    """The service references a publication of ``commit`` pushes: immutable tags first, then the channel."""
    tags = tags or (f"sha-{commit}", "main")
    return [publish_images.reference(service, tag) for tag in tags for service in publish_images.SERVICES]


def test_the_head_of_main_publishes_runtimes_then_its_images_by_commit_then_main(monkeypatch, checkout, capsys):
    commit = git(checkout, "rev-parse", "HEAD")
    registry = Registry()
    monkeypatch.setattr(subprocess, "run", registry)
    assert publish_images.publish("autograder", "local", checkout) == RUNTIMES + services(commit)
    # Runtime images first: the Action and sandbox manager pull the ones they pin.
    assert registry.pushed() == RUNTIMES + services(commit)
    tags = [args for args in registry.effects if args[:2] == ["docker", "tag"]]
    # Exactly the local images `make test-images` built and checked.
    assert tags == [["docker", "tag", f"autograder-{service}:local", publish_images.reference(service, tag)]
                    for tag in (f"sha-{commit}", "main") for service in publish_images.SERVICES]
    assert "::warning::" not in capsys.readouterr().out


def test_published_runtime_references_are_never_overwritten(monkeypatch, checkout):
    commit = git(checkout, "rev-parse", "HEAD")
    registry = Registry(present=RUNTIMES)
    monkeypatch.setattr(subprocess, "run", registry)
    publish_images.publish("autograder", "local", checkout)
    assert registry.pushed() == services(commit)


def test_a_commit_that_is_no_longer_the_head_of_main_publishes_nothing(monkeypatch, checkout, tmp_path, capsys):
    # Verification time differs per commit, so an older commit can finish after a
    # newer one: publishing it would move `main` (and @main consumers) back.
    newer = tmp_path / "newer"
    REAL_RUN(["git", "clone", "-q", str(tmp_path / "origin.git"), str(newer)], check=True, capture_output=True)
    git(newer, "commit", "-q", "--allow-empty", "-m", "newer")
    git(newer, "push", "-q", "origin", "HEAD:main")
    registry = Registry()
    monkeypatch.setattr(subprocess, "run", registry)
    assert publish_images.publish("autograder", "local", checkout) == []
    assert registry.effects == []
    assert git(newer, "rev-parse", "HEAD") in capsys.readouterr().out


def test_a_checkout_without_a_main_on_origin_is_an_error(monkeypatch, tmp_path):
    clone = tmp_path / "lonely"
    REAL_RUN(["git", "init", "-q", str(clone)], check=True)
    REAL_RUN(["git", "-C", str(clone), "remote", "add", "origin", str(tmp_path / "missing.git")], check=True)
    REAL_RUN(["git", "-C", str(clone), "-c", "user.name=t", "-c", "user.email=t@example.invalid",
              "commit", "-q", "--allow-empty", "-m", "x"], check=True)
    registry = Registry()
    monkeypatch.setattr(subprocess, "run", registry)
    with pytest.raises(subprocess.CalledProcessError):
        publish_images.publish("autograder", "local", clone)
    assert registry.effects == []


def test_a_push_the_registry_does_not_serve_fails_the_publication(monkeypatch, checkout):
    # Confirmed as the workflow token sees the registry: a lost push is red, never green.
    lost = publish_images.reference("api", "main")
    monkeypatch.setattr(subprocess, "run", Registry(lose=[lost]))
    with pytest.raises(RuntimeError, match=lost):
        publish_images.publish("autograder", "local", checkout)


def test_a_private_package_is_published_with_a_warning_not_a_failure(monkeypatch, checkout, capsys):
    # Visibility is an organization setting, made public once per package by an admin:
    # the token can push, but anonymous runners cannot pull until then.
    commit = git(checkout, "rev-parse", "HEAD")
    registry = Registry(public=False)
    monkeypatch.setattr(subprocess, "run", registry)
    assert publish_images.publish("autograder", "local", checkout) == RUNTIMES + services(commit)
    out = capsys.readouterr().out
    for reference in RUNTIMES + services(commit, ("main",)):
        assert f"::warning::{reference}" in out
    assert "public" in out


def test_packages_that_already_exist_privately_are_a_warning_not_a_failure(monkeypatch, checkout, capsys):
    # The runtime and API packages already exist on GHCR as private packages, so the
    # first publication from main meets "unauthorized" for those it does not push.
    registry = Registry(present=RUNTIMES, public=False)
    monkeypatch.setattr(subprocess, "run", registry)
    publish_images.publish("autograder", "local", checkout)
    out = capsys.readouterr().out
    for reference in RUNTIMES:
        assert f"::warning::{reference}" in out


@pytest.mark.parametrize("stderr", ['Get "https://ghcr.io/v2/x/y/manifests/1": unauthorized',  # private
                                    'Get "https://ghcr.io/v2/x/y/manifests/1": denied'])       # not created
def test_a_private_or_missing_package_is_not_anonymously_pullable(monkeypatch, stderr):
    seen = []
    monkeypatch.setattr(subprocess, "run", lambda args, **kwargs: seen.append(kwargs["env"]["DOCKER_CONFIG"]) or
                        subprocess.CompletedProcess(args, 1, "", stderr))
    assert sandbox_images.anonymously_pullable("ghcr.io/x/y:1") is False
    assert len(seen) == 1 and not Path(seen[0]).exists()  # an empty client configuration, removed afterwards


def test_an_unexpected_registry_answer_is_an_error_never_unpullable(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda args, **kwargs:
                        subprocess.CompletedProcess(args, 1, "", "dial tcp: i/o timeout"))
    with pytest.raises(RuntimeError, match="i/o timeout"):
        sandbox_images.anonymously_pullable("ghcr.io/x/y:1")
