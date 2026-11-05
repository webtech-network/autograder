"""ENV-04: the Action runs a released, prebuilt image, and a version is published once.

The image itself is built and checked against real Docker in ``tests/images/``.
"""
# pylint: disable=missing-function-docstring
import subprocess
from pathlib import Path

import pytest
import yaml

from scripts import action_image

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
            lines = "".join(f"{sha}\trefs/tags/0.6.0\n" for sha in self.tagged)
            return subprocess.CompletedProcess(args, 0, lines, "")
        assert kwargs.get("check") is True, args
        self.effects.append(args)
        return subprocess.CompletedProcess(args, 0, "", "")


@pytest.fixture
def action(tmp_path):
    path = tmp_path / "action.yml"
    path.write_text(yaml.safe_dump({"runs": {"image": "docker://ghcr.io/webtech-network/autograder-action:0.6.0"}}))
    return path


def test_release_tags_this_commit_then_pushes_the_tested_image(monkeypatch, action):
    boundary = Boundary()
    monkeypatch.setattr(subprocess, "run", boundary)
    action_image.publish("autograder-action:local", action)
    reference = "ghcr.io/webtech-network/autograder-action:0.6.0"
    assert boundary.effects == [["git", "tag", "0.6.0", HEAD], ["git", "push", "origin", "refs/tags/0.6.0"],
                                ["docker", "tag", "autograder-action:local", reference],
                                ["docker", "push", reference]]


def test_published_version_is_never_overwritten(monkeypatch, action):
    boundary = Boundary(published=True)
    monkeypatch.setattr(subprocess, "run", boundary)
    action_image.publish("autograder-action:local", action)
    assert boundary.effects == []


def test_interrupted_release_of_this_commit_resumes_with_the_image(monkeypatch, action):
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
