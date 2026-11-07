#!/usr/bin/env python3
"""Release a verified commit of ``main`` as a version, without rebuilding anything.

Run only by the hand-run Release workflow (``.github/workflows/release.yml``,
``make release``), given a commit ``C`` of ``main`` and a version ``V``. It
checks everything before it changes anything and refuses unless:

* ``V`` is ``MAJOR.MINOR.PATCH`` and ``C`` is a full commit SHA reachable from
  ``origin``'s ``main``;
* at ``C``, ``pyproject.toml`` says version ``V``, ``CHANGELOG.md`` has a
  ``## [V]`` section and ``action.yml`` runs the ``:main`` Action image;
* the ``Publish images from main`` job of a Verify run of ``C`` succeeded and
  the registry serves the API, sandbox manager and Action images as ``sha-<C>``;
* no git tag ``V`` exists on ``origin``, and no image is tagged ``V`` with
  other bytes than ``sha-<C>`` (an earlier, interrupted run of the same release
  left identical tags, which are kept).

Then it tags the ``sha-<C>`` manifests as ``V`` in the registry (by digest,
Action last), commits on top of ``C`` the one change that pins ``action.yml``'s
``runs.image`` to ``autograder-action:V``, pushes only the annotated tag ``V``
(the commit stays outside ``main``), and creates the GitHub Release ``V`` with
the changelog section as notes. ``@V`` therefore runs exactly the image verified
from ``C``, with ``C``'s interface.

Run as a module from the repository root:
``python -m scripts.release <commit> <version>``.
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Sequence

import yaml

from scripts import sandbox_images
from scripts.publish_images import (CHANNEL, ROOT, SERVICES, digest, reference, repository, retag, verified,
                                    warn_unless_public)

VERSION = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")
COMMIT = re.compile(r"[0-9a-f]{40}")
#: The name of the job in ``.github/workflows/verify.yml`` that publishes ``sha-<commit>``.
PUBLISH_JOB = "Publish images from main"


class Refused(Exception):
    """The release cannot proceed; nothing was changed by the check that raised it."""


@dataclass(frozen=True)
class Release:
    """What a checked release publishes: ``commit``'s images, digest by service, as ``version``."""
    commit: str
    version: str
    notes: str
    digests: Dict[str, str]


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout.strip()


def _gh(root: Path, *args: str) -> str:
    return subprocess.run(["gh", *args], cwd=root, capture_output=True, text=True, check=True).stdout


def _show(root: Path, commit: str, path: str) -> str:
    try:
        return _git(root, "show", f"{commit}:{path}")
    except subprocess.CalledProcessError:
        raise Refused(f"{commit} has no {path}") from None


def _image_line(tag: str) -> str:
    """The line of ``action.yml`` that makes it run the Action image tagged ``tag``."""
    return f'image: "docker://{reference("action", tag)}"'


def changelog_section(changelog: str, version: str) -> Optional[str]:
    """The body of the ``## [version]`` section of a Keep a Changelog file, or None."""
    heading = re.compile(rf"^## \[{re.escape(version)}\](?: - \d{{4}}-\d{{2}}-\d{{2}})?[ \t]*$", re.M)
    found = heading.search(changelog)
    if found is None:
        return None
    following = re.search(r"^(## |\[[^\]]+\]: )", changelog[found.end():], re.M)
    body = changelog[found.end():found.end() + following.start() if following else None].strip()
    return body or None


def release_notes(section: str, version: str) -> str:
    """``section`` with its repository-relative links made absolute at the release tag."""
    return re.sub(r"\]\((?!https?:|mailto:|#)([^)\s]+)\)",
                  lambda link: f"]({sandbox_images.SOURCE}/blob/{version}/{link.group(1)})", section)


def publish_succeeded(root: Path, commit: str) -> bool:
    """Whether the publish job of a push run of the Verify workflow for ``commit`` succeeded."""
    runs = json.loads(_gh(root, "api", "repos/{owner}/{repo}/actions/workflows/verify.yml/runs"
                                       f"?head_sha={commit}&event=push&per_page=100"))["workflow_runs"]
    for run in runs:
        jobs = json.loads(_gh(root, "api", f"repos/{{owner}}/{{repo}}/actions/runs/{run['id']}/jobs"
                                           "?filter=all&per_page=100"))["jobs"]
        if any(job["name"] == PUBLISH_JOB and job["conclusion"] == "success" for job in jobs):
            return True
    return False


def check(commit: str, version: str, root: Path = ROOT) -> Release:
    """Every precondition of releasing ``commit`` as ``version``; raise :class:`Refused` at the first unmet one."""
    if not VERSION.fullmatch(version):
        raise Refused(f"version {version!r} is not MAJOR.MINOR.PATCH")
    if not COMMIT.fullmatch(commit):
        raise Refused(f"commit {commit!r} is not a full lowercase commit SHA")
    _git(root, "fetch", "--quiet", "origin", "+refs/heads/main:refs/remotes/origin/main")
    if subprocess.run(["git", "merge-base", "--is-ancestor", commit, "refs/remotes/origin/main"],
                      cwd=root, capture_output=True, check=False).returncode != 0:
        raise Refused(f"{commit} is not a commit of origin's main")
    declared = tomllib.loads(_show(root, commit, "pyproject.toml"))["project"]["version"]
    if declared != version:
        raise Refused(f"pyproject.toml at {commit} declares version {declared}, not {version}")
    section = changelog_section(_show(root, commit, "CHANGELOG.md"), version)
    if section is None:
        raise Refused(f"CHANGELOG.md at {commit} has no non-empty ## [{version}] section")
    action = _show(root, commit, "action.yml")
    image = yaml.safe_load(action)["runs"]["image"]
    if image != f"docker://{reference('action', CHANNEL)}" or action.count(_image_line(CHANNEL)) != 1:
        raise Refused(f"action.yml at {commit} runs {image}, not exactly the {CHANNEL} image its release pins")
    if _git(root, "ls-remote", "--tags", "origin", f"refs/tags/{version}"):
        raise Refused(f"tag {version} already exists on origin; a release is never overwritten")
    if not publish_succeeded(root, commit):
        raise Refused(f"no '{PUBLISH_JOB}' job succeeded for {commit}: release only a verified, published commit")
    digests = {}
    for service in SERVICES:
        digests[service] = digest(verified(service, commit))
        if digests[service] is None:
            raise Refused(f"{verified(service, commit)} is not published: {commit} was not the head of main "
                          "when it was verified; choose a commit whose images were published")
        existing = digest(reference(service, version))
        if existing not in (None, digests[service]):
            raise Refused(f"{reference(service, version)} already exists with other bytes ({existing}); "
                          "a released image is never overwritten")
    return Release(commit, version, release_notes(section, version), digests)


def pin_action(root: Path, commit: str, version: str) -> str:
    """Commit, on top of ``commit`` and outside any branch, the pin of ``runs.image`` to ``version``; return it."""
    with tempfile.TemporaryDirectory() as directory:
        worktree = Path(directory) / "release"
        _git(root, "worktree", "add", "--quiet", "--detach", str(worktree), commit)
        try:
            action = worktree / "action.yml"
            action.write_text(action.read_text(encoding="utf-8").replace(_image_line(CHANNEL), _image_line(version)),
                              encoding="utf-8")
            _git(worktree, "commit", "--quiet", "--message", f"release: {version}\n\n"
                 f"Pin runs.image to {reference('action', version)}, the image verified from {commit}.",
                 "--", "action.yml")
            return _git(worktree, "rev-parse", "HEAD")
        finally:
            _git(root, "worktree", "remove", "--force", str(worktree))


def release(commit: str, version: str, root: Path = ROOT) -> Release:
    """Check, then release ``commit`` as ``version``: image tags, the pinned commit and its tag, the GitHub Release."""
    checked = check(commit, version, root)
    for service in SERVICES:
        if digest(reference(service, version)) != checked.digests[service]:
            retag(f"{repository(verified(service, commit))}@{checked.digests[service]}", reference(service, version))
    warn_unless_public([reference(service, version) for service in SERVICES])
    pinned = pin_action(root, commit, version)
    _git(root, "tag", "--annotate", version, pinned, "--message", version)
    _git(root, "push", "--quiet", "origin", f"refs/tags/{version}")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md") as notes:
        notes.write(checked.notes)
        notes.flush()
        _gh(root, "release", "create", version, "--verify-tag", "--title", version, "--notes-file", notes.name)
    print(f"Released {commit} as {version}: tag {version} at {pinned}; "
          + ", ".join(reference(service, version) for service in SERVICES), flush=True)
    return checked


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Command line: ``<commit> <version>``."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("commit", help="full SHA of a commit of main whose images were published")
    parser.add_argument("version", help="MAJOR.MINOR.PATCH, as pyproject.toml declares it at that commit")
    args = parser.parse_args(argv)
    try:
        release(args.commit, args.version)
    except Refused as refused:
        print(f"::error::Release refused, nothing changed: {refused}", flush=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(exc.stderr or "", file=sys.stderr, flush=True)
        sys.exit(exc.returncode)
