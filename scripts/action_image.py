#!/usr/bin/env python3
"""Show or publish the Action image that ``action.yml`` pins.

``action.yml`` names ``docker://ghcr.io/webtech-network/autograder-action:<version>``,
so a workflow pulls that image instead of building one. Raising ``<version>`` in
``action.yml`` is the release: after every verification job of a ``main`` commit
passed, CI builds and tests the image from scratch (``make test-images``) and
``publish`` pushes exactly that image under the pinned reference and tags the commit
``<version>``. A version is published once: an existing reference is never
overwritten, and a ``<version>`` tag on another commit stops the release.

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


def publish(local_image: str, action: Path = ROOT / "action.yml") -> None:
    """Push ``local_image`` as the pinned reference unless it is published, and tag this commit."""
    reference, version = pinned(action)
    if published(reference):
        print(f"{reference} is already published; published versions are immutable", flush=True)
        return
    head = _output("git", "rev-parse", "HEAD")
    tagged = _output("git", "ls-remote", "origin", f"refs/tags/{version}^{{}}", f"refs/tags/{version}").split()
    if tagged and head not in tagged:
        raise RuntimeError(f"tag {version} already names another commit ({tagged[0]}); raise the version in "
                           "action.yml instead of reusing it")
    if not tagged:
        subprocess.run(["git", "tag", version, head], check=True)
        subprocess.run(["git", "push", "origin", f"refs/tags/{version}"], check=True)
    subprocess.run(["docker", "tag", local_image, reference], check=True)
    subprocess.run(["docker", "push", reference], check=True)


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Command line: ``ref`` prints the pinned reference; ``publish <local image>`` releases it."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("ref", help="print the image reference action.yml pins")
    release = commands.add_parser("publish", help="publish a tested local image under that reference")
    release.add_argument("local_image")
    args = parser.parse_args(argv)
    if args.command == "ref":
        print(pinned()[0])
    else:
        publish(args.local_image)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
