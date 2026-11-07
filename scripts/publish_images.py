#!/usr/bin/env python3
"""Publish the images a verified commit of ``main`` consists of.

``main`` is the development channel; releases re-tag what it published
(``scripts/release.py``). After every verification job of a push to ``main``
passed, the ``publish`` job of ``.github/workflows/verify.yml`` rebuilds and
checks the images from that commit (``make test-images``,
``make sandbox-build-all``) and runs this script (``make publish-images``),
which:

1. publishes nothing unless the commit is still the head of ``origin``'s
   ``main``: verification takes a different time per commit, so an older commit
   can finish after a newer one and must not move ``main`` back;
2. pushes each runtime image (``sandbox_manager/images``, the references
   ``sandbox_config.yml`` pins) that the registry does not have yet; those
   references are derived from content and never overwritten. They go first
   because the Action and the sandbox manager pull them;
3. pushes the API, sandbox manager and Action images as
   ``ghcr.io/webtech-network/autograder-<name>:sha-<commit>`` unless that
   reference already exists: it is never overwritten, so a re-run of the job
   keeps the bytes the first run published;
4. points ``:main`` at exactly those ``sha-<commit>`` manifests, by digest and
   without rebuilding. ``action.yml`` runs ``:main``, so
   ``webtech-network/autograder@main`` pulls the image of the newest verified commit;
5. confirms every reference with the registry as the workflow token sees it (a
   lost push fails the job), and warns for each package an anonymous runner
   cannot pull yet: an organization admin makes a new package public once.

Run as a module from the repository root:
``python -m scripts.publish_images <local prefix> <local tag>``.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence

from scripts import sandbox_images

ROOT = Path(__file__).resolve().parents[1]
#: The moving tag of the newest verified ``main`` commit, the one ``action.yml`` runs on ``main``.
CHANNEL = "main"
#: The images ``make images`` builds, as ``<prefix>-<name>:<tag>``; the Action's tags move last.
SERVICES = ("api", "sandbox-manager", "action")


def reference(service: str, tag: str) -> str:
    """The published reference of one of :data:`SERVICES` under ``tag``."""
    return f"{sandbox_images.REGISTRY}/autograder-{service}:{tag}"


def verified(service: str, commit: str) -> str:
    """The immutable reference of ``service`` as published from ``commit``."""
    return reference(service, f"sha-{commit}")


def repository(ref: str) -> str:
    """``ref`` without its tag or digest: ``ghcr.io/org/name:tag`` -> ``ghcr.io/org/name``."""
    name = ref.split("@", 1)[0]
    path, _, last = name.rpartition("/")
    return f"{path}/{last.split(':', 1)[0]}"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout.strip()


def _docker(*args: str) -> None:
    subprocess.run(["docker", *args], check=True)


def digest(ref: str) -> Optional[str]:
    """The manifest digest the registry serves for ``ref``, or None when it has no such reference.

    As in :func:`sandbox_images.published`, an unexpected answer is an error, never "absent".
    """
    found = subprocess.run(["docker", "buildx", "imagetools", "inspect", ref, "--format", "{{json .Manifest}}"],
                           capture_output=True, text=True, check=False)
    if found.returncode == 0:
        return json.loads(found.stdout)["digest"]
    if sandbox_images.ABSENT.search(found.stderr):
        return None
    raise RuntimeError(f"cannot tell whether {ref} is published: {found.stderr.strip()}")


def retag(source: str, target: str) -> str:
    """Point ``target`` at the manifest ``source`` names, in the registry, without rebuilding; return its digest.

    ``--prefer-index=false`` copies a single image manifest as it is instead of
    wrapping it in a new index, so ``target`` serves the same digest as ``source``.
    """
    expected = digest(source)
    if expected is None:
        raise RuntimeError(f"{source} is not published")
    _docker("buildx", "imagetools", "create", "--prefer-index=false", "--tag", target,
            f"{repository(source)}@{expected}")
    actual = digest(target)
    if actual != expected:
        raise RuntimeError(f"{target} serves {actual}, not {expected} of {source}")
    return expected


def warn_unless_public(refs: Sequence[str]) -> None:
    """Warn for each reference a client without credentials, such as a hosted runner, cannot pull."""
    for ref in [ref for ref in refs if not sandbox_images.anonymously_pullable(ref)]:
        print(f"::warning::{ref} is published but an anonymous runner cannot pull it: an organization admin "
              "must make its package public once (docs/github_action/README.md#versions-and-images).", flush=True)


def publish(local_prefix: str, local_tag: str, root: Path = ROOT) -> List[str]:
    """Publish this checkout's locally built images if it is still the head of ``main``; return what was pushed."""
    commit = _git(root, "rev-parse", "HEAD")
    listed = _git(root, "ls-remote", "--exit-code", "origin", "refs/heads/main")
    head = listed.split()[0]
    if head != commit:
        print(f"::notice::main moved to {head}; {commit} publishes nothing.", flush=True)
        return []
    runtimes = sandbox_images.catalog()
    pushed = sandbox_images.publish(runtimes)
    for service in SERVICES:
        immutable = verified(service, commit)
        if digest(immutable) is not None:
            print(f"{immutable} is already published; published references are immutable", flush=True)
            continue
        _docker("tag", f"{local_prefix}-{service}:{local_tag}", immutable)
        _docker("push", immutable)
        pushed.append(immutable)
    missing = [ref for ref in pushed if not sandbox_images.published(ref)]
    if missing:
        raise RuntimeError(f"pushed but not served by the registry: {', '.join(missing)}")
    for service in SERVICES:
        retag(verified(service, commit), reference(service, CHANNEL))
        pushed.append(reference(service, CHANNEL))
    warn_unless_public([image.ref for image in runtimes] + [reference(service, CHANNEL) for service in SERVICES])
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
