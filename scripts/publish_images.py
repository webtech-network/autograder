#!/usr/bin/env python3
"""Publish the images a verified commit of ``main`` consists of.

There are no releases before 1.0.0: ``main`` is the channel. After every
verification job of a push to ``main`` passed, the ``publish`` job of
``.github/workflows/verify.yml`` rebuilds and checks the images from that commit
(``make test-images``, ``make sandbox-build-all``) and runs this script
(``make publish-images``), which:

1. publishes nothing unless the commit is still the head of ``origin``'s
   ``main``: verification takes a different time per commit, so an older commit
   can finish after a newer one and must not move ``main`` back;
2. pushes each runtime image (``sandbox_manager/images``, the references
   ``sandbox_config.yml`` pins) that the registry does not have yet; those
   references are derived from content and never overwritten. They go first
   because the Action and the sandbox manager pull them;
3. pushes the API, sandbox manager and Action images as
   ``ghcr.io/webtech-network/autograder-<name>:sha-<commit>`` (immutable), then
   as ``:main``, which ``action.yml`` runs, so ``webtech-network/autograder@main``
   pulls the image built and verified from the newest verified commit;
4. confirms every pushed reference with the registry as the workflow token
   sees it (a lost push fails the job), and warns for each package an anonymous
   runner cannot pull yet: an organization admin makes a new package public once.

Run as a module from the repository root:
``python -m scripts.publish_images <local prefix> <local tag>``.
"""
import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Optional, Sequence

from scripts import sandbox_images

ROOT = Path(__file__).resolve().parents[1]
#: The moving tag of the newest verified ``main`` commit, the one ``action.yml`` runs.
CHANNEL = "main"
#: The images ``make images`` builds, as ``<prefix>-<name>:<tag>``; the Action's ``main`` moves last.
SERVICES = ("api", "sandbox-manager", "action")


def reference(service: str, tag: str) -> str:
    """The published reference of one of :data:`SERVICES` under ``tag``."""
    return f"{sandbox_images.REGISTRY}/autograder-{service}:{tag}"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout.strip()


def _docker(*args: str) -> None:
    subprocess.run(["docker", *args], check=True)


def publish(local_prefix: str, local_tag: str, root: Path = ROOT) -> List[str]:
    """Publish this checkout's locally built images if it is still the head of ``main``; return what was pushed."""
    commit = _git(root, "rev-parse", "HEAD")
    listed = _git(root, "ls-remote", "--exit-code", "origin", "refs/heads/main")
    head = listed.split()[0]
    if head != commit:
        print(f"::notice::main moved to {head}; {commit} publishes nothing.", flush=True)
        return []
    runtimes = sandbox_images.catalog()
    sandbox_images.publish(runtimes)
    pushed = [image.ref for image in runtimes]
    for tag in (f"sha-{commit}", CHANNEL):
        for service in SERVICES:
            remote = reference(service, tag)
            _docker("tag", f"{local_prefix}-{service}:{local_tag}", remote)
            _docker("push", remote)
            pushed.append(remote)
    missing = [ref for ref in pushed if not sandbox_images.published(ref)]
    if missing:
        raise RuntimeError(f"pushed but not served by the registry: {', '.join(missing)}")
    consumed = [image.ref for image in runtimes] + [reference(service, CHANNEL) for service in SERVICES]
    with tempfile.TemporaryDirectory() as anonymous:
        private = [ref for ref in consumed
                   if not sandbox_images.published(ref, env={**os.environ, "DOCKER_CONFIG": anonymous})]
    for ref in private:
        print(f"::warning::{ref} is published but an anonymous runner cannot pull it: an organization admin "
              "must make its package public once (docs/github_action/README.md#versions-and-images).", flush=True)
    print(f"Published {commit} as {CHANNEL}: {', '.join(pushed)}", flush=True)
    return pushed


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Command line: ``<local prefix> <local tag>`` names the images ``make images`` built."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("local_prefix", help="IMAGE_PREFIX of the local images, e.g. autograder")
    parser.add_argument("local_tag", help="IMAGE_TAG of the local images, e.g. local")
    args = parser.parse_args(argv)
    publish(args.local_prefix, args.local_tag)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
