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
fails while the pinned image is not anonymously pullable. A version is published
once: an existing reference is never overwritten, and a ``<version>`` tag on
another commit stops the release.

Run as a module from the repository root: ``python -m scripts.action_image ref``.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, Sequence, Tuple

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


def _output(*args: str) -> str:
    return subprocess.run(list(args), capture_output=True, text=True, check=True).stdout.strip()


def check(action: Path = ROOT / "action.yml") -> None:
    """Exit 1 unless the pinned image is pullable without credentials, as on a consumer's runner."""
    reference, _ = pinned(action)
    if not published(reference):
        print(f"action.yml pins {reference}, which an anonymous runner cannot pull, so every "
              "`webtech-network/autograder@main` workflow would fail. Publish it first: run the Verify "
              "workflow (workflow_dispatch) on this branch. A new package must then be made public "
              "(docs/github_action/README.md#releasing-a-version).", file=sys.stderr, flush=True)
        sys.exit(1)
    print(f"{reference} is published and public", flush=True)


def publish(local_image: str, action: Path = ROOT / "action.yml") -> None:
    """Push ``local_image`` as the pinned reference unless it is published, then tag this commit.

    The image goes first: the tag is what ``uses: ...@<version>`` resolves, so it
    never exists without its image. An interrupted release resumes on a re-run.
    """
    reference, version = pinned(action)
    head = _output("git", "rev-parse", "HEAD")
    tagged = _output("git", "ls-remote", "origin", f"refs/tags/{version}^{{}}", f"refs/tags/{version}").split()
    if tagged and head not in tagged:
        raise RuntimeError(f"tag {version} already names another commit ({tagged[0]}); raise the version in "
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
    commands.add_parser("check", help="fail unless that reference is anonymously pullable")
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
