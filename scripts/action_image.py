#!/usr/bin/env python3
"""Show, check or publish the Action image that ``action.yml`` pins.

``action.yml`` names ``docker://ghcr.io/webtech-network/autograder-action:<version>``,
so a workflow pulls that image instead of building one. Consumers use
``webtech-network/autograder@main``, so ``main`` must only ever name an image that
an anonymous runner can pull. The release therefore happens before the pin
reaches ``main``: a maintainer runs the Verify workflow (``workflow_dispatch``) on
the branch that raises ``<version>``; after every verification job passed, CI
builds and tests the image from scratch (``make test-images``) and ``publish``
pushes exactly that image under the pinned reference, then tags the commit
``<version>``. ``check`` (CI, on pull requests into ``main`` and on ``main``)
fails unless the ``<version>`` tag is in the checked commit's history, nothing
the release consists of (``action.yml`` and every input of the image) changed
since that tag, and the pinned image and the runtime images its
``sandbox_config.yml`` pins (which the Action pulls on the runner) are
anonymously pullable. A version is
published once: an existing reference is never overwritten, and a ``<version>``
tag on another commit stops the release.

Run as a module from the repository root: ``python -m scripts.action_image ref``.
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import yaml

from scripts.sandbox_images import published

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = "ghcr.io/webtech-network/autograder-action"
_PINNED = re.compile(r"docker://" + re.escape(REPOSITORY) + r":(\d+\.\d+\.\d+)")


def pinned(action: Path = ROOT / "action.yml") -> Tuple[str, str]:
    """The image reference ``action.yml`` runs and its version."""
    image = yaml.safe_load(action.read_text(encoding="utf-8"))["runs"]["image"]
    match = _PINNED.fullmatch(image)
    if match is None:
        raise ValueError(f"action.yml must run a released image, docker://{REPOSITORY}:<x.y.z>; found {image!r}")
    return image.removeprefix("docker://"), match.group(1)


def released_paths(root: Path = ROOT) -> List[str]:
    """What a release consists of: ``action.yml``, which consumers read from the
    branch, and everything the Action image is built from (``Dockerfile.actions``,
    the ``.dockerignore`` filter and each build-context path it copies).

    A change to any of these after the ``<version>`` tag would make ``@main``
    disagree with the image it pins.
    """
    sources = []
    dockerfile = (root / "Dockerfile.actions").read_text(encoding="utf-8").replace("\\\n", " ")
    for line in dockerfile.splitlines():
        words = line.split()
        if not words or words[0].upper() not in ("COPY", "ADD"):
            continue
        if words[1].startswith("["):
            raise ValueError(f"Dockerfile.actions: write {words[0]} in shell form so its sources can be read: {line!r}")
        if any(word.startswith("--from") for word in words):
            continue  # another stage or image, pinned in the Dockerfile itself
        sources += [word for word in words[1:-1] if not word.startswith("--")]
    return ["action.yml", "Dockerfile.actions", ".dockerignore", *sources]


def runtimes(config: Path = ROOT / "sandbox_config.yml") -> List[str]:
    """The runtime image references ``sandbox_config.yml`` pins, which the Action image ships."""
    return sorted(set(yaml.safe_load(config.read_text(encoding="utf-8"))["runtimes"].values()))


def _output(*args: str, cwd: Optional[Path] = None) -> str:
    return subprocess.run(list(args), capture_output=True, text=True, check=True, cwd=cwd).stdout.strip()


def _tagged(version: str, cwd: Optional[Path] = None) -> Optional[str]:
    """The commit ``origin``'s ``<version>`` tag names (peeled when annotated), if the tag exists."""
    listed = _output("git", "ls-remote", "origin", f"refs/tags/{version}", f"refs/tags/{version}^{{}}", cwd=cwd)
    refs = {ref: sha for sha, ref in (line.split() for line in listed.splitlines())}
    return refs.get(f"refs/tags/{version}^{{}}", refs.get(f"refs/tags/{version}"))


def _stop(message: str) -> None:
    print(message, file=sys.stderr, flush=True)
    sys.exit(1)


def check(root: Path = ROOT) -> None:
    """Exit 1 unless the checked commit is the pinned release: released from its history, unchanged since, public.

    The ``<version>`` tag names the commit the image was built from; it must be an
    ancestor of the checked commit, so the image ``@main`` runs provably comes
    from merged history (not from a dispatch on an unmerged or rewritten commit).
    No released path may differ between that commit and this one, so ``action.yml``
    and the image ``@main`` runs are exactly what was released together: any
    change to the interface or the image needs a new version and release.
    The registry is asked with an empty ``DOCKER_CONFIG``, as a consumer's runner
    asks: a private package reads as absent even where the caller is logged in.
    The runtime images the release pins must be anonymously pullable too: the
    Action pulls the selected language's image on the runner (ENV-03).
    """
    reference, version = pinned(root / "action.yml")
    release = "run the Verify workflow (workflow_dispatch) on the branch that raises the version"
    tagged = _tagged(version, cwd=root)
    if not tagged:
        _stop(f"action.yml pins {version}, which has not been released (no `{version}` tag): {release} "
              "(docs/github_action/README.md#releasing-a-version).")
    ancestor = subprocess.run(["git", "merge-base", "--is-ancestor", tagged, "HEAD"],
                              capture_output=True, text=True, check=False, cwd=root)
    if ancestor.returncode == 1:
        _stop(f"tag {version} ({tagged}) is not in this commit's history, so {reference} was not built from "
              "merged code. Merge the release branch with a merge commit (not squash or rebase), or raise the "
              f"version and release again (docs/github_action/README.md#releasing-a-version).")
    if ancestor.returncode != 0:
        raise RuntimeError(f"cannot tell whether tag {version} is in this commit's history (a shallow clone needs "
                           f"full history): {ancestor.stderr.strip()}")
    changed = _output("git", "diff", "--name-only", tagged, "HEAD", "--", *released_paths(root), cwd=root)
    if changed:
        files = changed.splitlines()
        listed = ", ".join(files[:10]) + (f" and {len(files) - 10} more" if len(files) > 10 else "")
        _stop(f"the Action changed after {version} was released, so `@main` would run this action.yml or code "
              f"with the {version} image built without it: {listed}. Raise the version "
              f"in action.yml and {release} (docs/github_action/README.md#releasing-a-version).")
    with tempfile.TemporaryDirectory() as anonymous:
        pullable = published(reference, env={**os.environ, "DOCKER_CONFIG": anonymous})
        private = [runtime for runtime in runtimes(root / "sandbox_config.yml")
                   if not published(runtime, env={**os.environ, "DOCKER_CONFIG": anonymous})]
    if not pullable:
        _stop(f"action.yml pins {reference}, which an anonymous runner cannot pull, so every "
              "`webtech-network/autograder@main` workflow would fail. Publish it first: "
              f"{release}. A new package must then be made public "
              "(docs/github_action/README.md#releasing-a-version).")
    if private:
        _stop(f"The Action runs submissions in the runtime images sandbox_config.yml pins, and an anonymous "
              f"runner cannot pull {', '.join(private)}, so execution-based grading would fail. They are "
              "published from main (sandbox-images.yml); make each new package public "
              "(docs/github_action/README.md#releasing-a-version).")
    print(f"{reference} was released from this history, nothing it consists of changed since, and it is "
          "published and public, with its runtime images", flush=True)


def publish(local_image: str, action: Path = ROOT / "action.yml") -> None:
    """Push ``local_image`` as the pinned reference unless it is published, then tag this commit.

    The image goes first: the tag is what ``uses: ...@<version>`` resolves, so it
    never exists without its image. An interrupted release resumes on a re-run.
    """
    reference, version = pinned(action)
    head = _output("git", "rev-parse", "HEAD")
    tagged = _tagged(version)
    if tagged and tagged != head:
        raise RuntimeError(f"tag {version} already names another commit ({tagged}); raise the version in "
                           "action.yml instead of reusing it")
    if published(reference):
        print(f"{reference} is already published; published versions are immutable", flush=True)
    else:
        subprocess.run(["docker", "tag", local_image, reference], check=True)
        subprocess.run(["docker", "push", reference], check=True)
    if not tagged:
        subprocess.run(["git", "tag", version, head], check=True)
        subprocess.run(["git", "push", "origin", f"refs/tags/{version}"], check=True)


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Command line: ``ref`` prints the pinned reference, ``check`` gates it, ``publish <local image>`` releases it."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("ref", help="print the image reference action.yml pins")
    commands.add_parser("check", help="fail unless that version was released from this history, nothing it "
                                        "consists of changed since, and it and its runtime images are "
                                        "anonymously pullable")
    release = commands.add_parser("publish", help="publish a tested local image under that reference")
    release.add_argument("local_image")
    args = parser.parse_args(argv)
    if args.command == "ref":
        print(pinned()[0])
    elif args.command == "check":
        check()
    else:
        publish(args.local_image)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
