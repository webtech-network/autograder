"""REL-01: a release re-tags the images verified from one commit of main and pins the Action to them.

The git side is real: a bare ``origin`` and the clone the Release workflow
checks out. The registry is the docker CLI and GitHub is the ``gh`` CLI, both
scripted at the subprocess boundary, with their effects recorded.
"""
# pylint: disable=missing-function-docstring,redefined-outer-name
import json
import re
import subprocess
import tomllib
from pathlib import Path

import pytest
import yaml

import autograder
from scripts import publish_images, release
from tests.unit.test_publish_images import REAL_RUN, Registry, fake_digest, git

ROOT = Path(__file__).resolve().parents[2]
VERSION = "1.0.0"
CHANGELOG = """# Changelog

## [Unreleased]

## [1.0.0] - 2026-11-06

### Changed
- Everything; see the [migration notes](docs/contracts/DECISIONS.md#migration-notes)
  and [the site](https://example.invalid/x).

## [0.9.0] - 2026-01-01

- Older.

[1.0.0]: https://github.com/webtech-network/autograder/releases/tag/1.0.0
"""


class GitHub(Registry):
    """The registry plus the ``gh`` CLI: workflow runs of verify.yml, and the Releases created."""

    def __init__(self, *, publish="success", **kwargs):
        super().__init__(**kwargs)
        self.publish = publish  # conclusion of the commit's publish job; None: no run at all
        self.releases = []

    def __call__(self, args, **kwargs):
        if args[0] != "gh":
            return super().__call__(args, **kwargs)
        assert kwargs.get("check") is True, args
        if args[:2] == ["gh", "api"] and "/actions/workflows/verify.yml/runs?" in args[2]:
            assert "event=push" in args[2]
            runs = [] if self.publish is None else [{"id": 7, "head_sha": args[2].split("head_sha=")[1][:40]}]
            return subprocess.CompletedProcess(args, 0, json.dumps({"workflow_runs": runs}), "")
        if args[:2] == ["gh", "api"] and args[2].startswith("repos/{owner}/{repo}/actions/runs/7/jobs"):
            jobs = [{"name": "Core path (make verify)", "conclusion": "success"},
                    {"name": release.PUBLISH_JOB, "conclusion": self.publish}]
            return subprocess.CompletedProcess(args, 0, json.dumps({"jobs": jobs}), "")
        if args[:3] == ["gh", "release", "create"]:
            notes = Path(args[args.index("--notes-file") + 1]).read_text(encoding="utf-8")
            self.releases.append((args, notes))
            return subprocess.CompletedProcess(args, 0, "", "")
        raise AssertionError(f"unexpected gh call: {args}")


@pytest.fixture
def repository(tmp_path, monkeypatch):
    """``(origin, checkout, C)``: C, the head of main, as the publish job left it, and the workflow's clone."""
    for key, value in {"GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig"), "GIT_CONFIG_NOSYSTEM": "1",
                       "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                       "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid"}.items():
        monkeypatch.setenv(key, value)
    (tmp_path / "gitconfig").write_text("")
    origin, author = tmp_path / "origin.git", tmp_path / "author"
    REAL_RUN(["git", "init", "-q", "--bare", "-b", "main", str(origin)], check=True)
    REAL_RUN(["git", "clone", "-q", str(origin), str(author)], check=True, capture_output=True)
    commit(author, {"action.yml": (ROOT / "action.yml").read_text(encoding="utf-8"),
                    "pyproject.toml": f'[project]\nname = "autograder"\nversion = "{VERSION}"\n',
                    "CHANGELOG.md": CHANGELOG})
    git(author, "push", "-q", "origin", "HEAD:main")
    checkout = tmp_path / "checkout"
    REAL_RUN(["git", "clone", "-q", str(origin), str(checkout)], check=True, capture_output=True)
    return origin, checkout, git(author, "rev-parse", "HEAD")


def commit(clone, files, message="change"):
    for name, text in files.items():
        (clone / name).write_text(text, encoding="utf-8")
    git(clone, "add", *files)
    git(clone, "commit", "-q", "-m", message)


def published(commit_sha):
    """The registry after commit_sha's publish job: its images as sha-<commit> and main."""
    return {publish_images.reference(service, tag): fake_digest("verified", service)
            for service in publish_images.SERVICES for tag in (f"sha-{commit_sha}", "main")}


def versioned(version=VERSION):
    return [publish_images.reference(service, version) for service in publish_images.SERVICES]


def test_a_release_tags_the_verified_images_and_a_commit_that_only_pins_the_action(monkeypatch, repository):
    origin, checkout, verified = repository
    github = GitHub(present=published(verified))
    monkeypatch.setattr(subprocess, "run", github)
    release.release(verified, VERSION, checkout)

    # The images are the ones verified from C, re-tagged by digest (Action last); nothing is built or pushed.
    assert github.retagged() == versioned()
    for service in publish_images.SERVICES:
        assert github.present[publish_images.reference(service, VERSION)] == fake_digest("verified", service)
    assert not [args for args in github.effects if args[:2] in (["docker", "build"], ["docker", "push"],
                                                                 ["docker", "tag"])]
    # The tag names one commit on top of C, outside main, whose only change pins runs.image.
    tagged = git(origin, "rev-parse", f"{VERSION}^{{commit}}")
    assert git(origin, "cat-file", "-t", VERSION) == "tag"  # annotated
    assert git(origin, "rev-parse", f"{tagged}^") == verified
    assert git(origin, "rev-parse", "refs/heads/main") == verified
    assert git(origin, "branch", "--contains", tagged) == ""
    assert git(origin, "diff", "--name-only", verified, tagged) == "action.yml"
    changed = [line for line in git(origin, "diff", "-U0", verified, tagged).splitlines()
               if line[:1] in "+-" and not line.startswith(("+++", "---"))]
    assert changed == [f'-  image: "docker://{publish_images.reference("action", "main")}"',
                       f'+  image: "docker://{publish_images.reference("action", VERSION)}"']
    runs = yaml.safe_load(git(origin, "show", f"{VERSION}:action.yml"))["runs"]
    assert runs["image"] == f"docker://ghcr.io/webtech-network/autograder-action:{VERSION}"
    # The GitHub Release is created from that tag with the changelog section, links made absolute.
    [(args, notes)] = github.releases
    assert args[3] == VERSION and "--verify-tag" in args
    assert notes.startswith("### Changed\n- Everything")
    assert "Older" not in notes and "releases/tag" not in notes
    assert ("(https://github.com/webtech-network/autograder/blob/1.0.0/docs/contracts/DECISIONS.md"
            "#migration-notes)") in notes
    assert "(https://example.invalid/x)" in notes


def test_an_interrupted_release_resumes_without_touching_the_identical_image_tags(monkeypatch, repository):
    origin, checkout, verified = repository
    present = published(verified)
    present[publish_images.reference("api", VERSION)] = present[publish_images.verified("api", verified)]
    github = GitHub(present=present)
    monkeypatch.setattr(subprocess, "run", github)
    release.release(verified, VERSION, checkout)
    assert github.retagged() == versioned()[1:]
    assert git(origin, "rev-parse", f"{VERSION}^{{commit}}^") == verified


def refusal(monkeypatch, checkout, commit_sha, github, match, version=VERSION):
    """Release must refuse with ``match`` and change nothing: no registry write, tag or Release."""
    monkeypatch.setattr(subprocess, "run", github)
    before = dict(github.present)
    with pytest.raises(release.Refused, match=match):
        release.release(commit_sha, version, checkout)
    assert github.effects == [] and github.releases == [] and github.present == before
    assert git(checkout, "ls-remote", "--tags", "origin") == ""


@pytest.mark.parametrize("version", ["v1.0.0", "1.0", "01.0.0", "1.0.0-rc.1", ""])
def test_a_version_that_is_not_major_minor_patch_is_refused(monkeypatch, repository, version):
    _, checkout, verified = repository
    refusal(monkeypatch, checkout, verified, GitHub(present=published(verified)), "MAJOR.MINOR.PATCH", version)


def test_an_abbreviated_commit_is_refused(monkeypatch, repository):
    _, checkout, verified = repository
    refusal(monkeypatch, checkout, verified[:12], GitHub(present=published(verified)), "full lowercase commit SHA")


def test_a_commit_outside_main_is_refused(monkeypatch, repository, tmp_path):
    origin, checkout, verified = repository
    branch = tmp_path / "branch"
    REAL_RUN(["git", "clone", "-q", str(origin), str(branch)], check=True, capture_output=True)
    commit(branch, {"README.md": "x"})
    git(branch, "push", "-q", "origin", "HEAD:refs/heads/feature")
    elsewhere = git(branch, "rev-parse", "HEAD")
    refusal(monkeypatch, checkout, elsewhere, GitHub(present=published(elsewhere)), "not a commit of origin's main")


def test_a_version_pyproject_does_not_declare_is_refused(monkeypatch, repository):
    _, checkout, verified = repository
    refusal(monkeypatch, checkout, verified, GitHub(present=published(verified)),
            "declares version 1.0.0, not 1.0.1", "1.0.1")


def test_a_version_without_a_changelog_section_is_refused(monkeypatch, repository, tmp_path):
    origin, checkout, _ = repository
    author = tmp_path / "author"
    commit(author, {"pyproject.toml": '[project]\nname = "autograder"\nversion = "1.1.0"\n'})
    git(author, "push", "-q", "origin", "HEAD:main")
    head = git(author, "rev-parse", "HEAD")
    refusal(monkeypatch, checkout, head, GitHub(present=published(head)), r"no non-empty ## \[1.1.0\] section", "1.1.0")
    assert git(origin, "rev-parse", "refs/heads/main") == head


@pytest.mark.parametrize("conclusion", [None, "failure", "cancelled", "skipped"])
def test_a_commit_whose_publish_job_did_not_succeed_is_refused(monkeypatch, repository, conclusion):
    _, checkout, verified = repository
    refusal(monkeypatch, checkout, verified, GitHub(present=published(verified), publish=conclusion),
            "no 'Publish images from main' job succeeded")


def test_a_commit_main_had_moved_past_when_it_was_verified_is_refused(monkeypatch, repository):
    # Its publish job succeeded but published nothing: there is no sha-<C> to release.
    _, checkout, verified = repository
    refusal(monkeypatch, checkout, verified, GitHub(present=published("0" * 40)), "is not published")


def test_an_existing_release_tag_is_never_overwritten(monkeypatch, repository, tmp_path):
    origin, checkout, verified = repository
    author = tmp_path / "author"
    git(author, "tag", VERSION)
    git(author, "push", "-q", "origin", f"refs/tags/{VERSION}")
    github = GitHub(present=published(verified))
    monkeypatch.setattr(subprocess, "run", github)
    with pytest.raises(release.Refused, match="tag 1.0.0 already exists"):
        release.release(verified, VERSION, checkout)
    assert github.effects == [] and github.releases == []
    assert git(origin, "rev-parse", f"refs/tags/{VERSION}") == verified


def test_an_existing_version_image_with_other_bytes_is_never_overwritten(monkeypatch, repository):
    _, checkout, verified = repository
    present = published(verified)
    present[publish_images.reference("action", VERSION)] = fake_digest("something else")
    refusal(monkeypatch, checkout, verified, GitHub(present=present), "already exists with other bytes")


def test_a_commit_whose_action_does_not_run_the_main_image_is_refused(monkeypatch, repository, tmp_path):
    origin, checkout, _ = repository
    author = tmp_path / "author"
    action = (ROOT / "action.yml").read_text(encoding="utf-8").replace("autograder-action:main", "autograder-action:9")
    commit(author, {"action.yml": action})
    git(author, "push", "-q", "origin", "HEAD:main")
    head = git(author, "rev-parse", "HEAD")
    refusal(monkeypatch, checkout, head, GitHub(present=published(head)), "not exactly the main image")
    assert git(origin, "rev-parse", "refs/heads/main") == head


def test_changelog_sections_end_at_the_next_heading_or_link_definitions():
    assert release.changelog_section(CHANGELOG, "0.9.0") == "- Older."
    assert release.changelog_section(CHANGELOG, "Unreleased") is None  # empty
    assert release.changelog_section(CHANGELOG, "2.0.0") is None
    assert release.changelog_section(CHANGELOG, "1.0.0").endswith("(https://example.invalid/x).")


# --- What the release of this repository's head would check ----------------------

def test_this_checkout_declares_one_version_with_a_changelog_section():
    version = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    assert release.VERSION.fullmatch(version)
    assert autograder.__version__ == version  # what the HTTP and sandbox APIs report
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    section = release.changelog_section(changelog, version)
    assert section
    assert "<!--" not in section  # the section is published verbatim as the GitHub Release notes
    assert re.search(rf"^\[{re.escape(version)}\]: https://github\.com/webtech-network/autograder/releases/tag/"
                     rf"{re.escape(version)}$", changelog, re.M)


def github_anchors(markdown: str) -> set[str]:
    """The heading anchors GitHub's file view gives ``markdown``: the release notes link there."""
    anchors, seen = set(), {}
    for heading in re.findall(r"^#{1,6}[ \t]+(.+?)[ \t]*#*$", re.sub(r"^```.*?^```", "", markdown, flags=re.M | re.S),
                              re.M):
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading)
        slug = re.sub(r"[^\w\- ]", "", text.lower()).replace(" ", "-")
        anchors.add(f"{slug}-{seen[slug]}" if slug in seen else slug)
        seen[slug] = seen.get(slug, 0) + 1
    return anchors


def test_github_anchors_follow_githubs_heading_slugs():
    assert github_anchors("## Upgrading to 1.0.0\n### Processes (ARC-08, COR-01)\n## `a` & [b](x.md)\n"
                          "```\n## code\n```\n## Upgrading to 1.0.0\n") == {
        "upgrading-to-100", "processes-arc-08-cor-01", "a--b", "upgrading-to-100-1"}


def test_every_link_of_the_changelog_reaches_its_file_and_heading():
    """The release notes are the changelog section with these links pointed at the tagged files."""
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    links = re.findall(r"\]\((?!https?:|mailto:)([^)\s#]*)(?:#([^)\s]+))?\)", changelog)
    assert len(links) > 20
    for target, anchor in links:
        page = ROOT / target if target else ROOT / "CHANGELOG.md"
        assert page.is_file(), target
        if anchor:
            assert anchor in github_anchors(page.read_text(encoding="utf-8")), f"{target}#{anchor}"


def test_the_http_and_sandbox_apis_report_the_release_version():
    from sandbox_manager.api import app  # pylint: disable=import-outside-toplevel
    from web.main import create_app  # pylint: disable=import-outside-toplevel
    from fastapi.testclient import TestClient  # pylint: disable=import-outside-toplevel
    assert app.version == autograder.__version__
    web = create_app(start_workers=False)
    assert web.version == autograder.__version__
    assert TestClient(web).get("/api/v1/health").json()["version"] == autograder.__version__
