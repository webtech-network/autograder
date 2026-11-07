#!/usr/bin/env python3
"""List, build and publish the sandbox runtime images (``sandbox_manager/images``).

Each ``Dockerfile.<name>`` is one runtime image. Its reference is derived, never
chosen: ``ghcr.io/webtech-network/autograder-sandbox-<name>:<tag>``, where the tag
is the first 12 hex digits of the Dockerfile's SHA-256. Editing a Dockerfile
therefore yields a new reference, which ``sandbox_config.yml`` must then name
(a unit test enforces it). ``publish`` never overwrites a reference that already
exists in the registry, so a rebuild cannot change what students run.

Images are built without a build context: the Dockerfile is sent on stdin, so no
file of the checkout (``.env``, ``.venv``, ``data/``...) can enter an image.
"""
import argparse
import hashlib
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Mapping, Optional, Sequence, Tuple

REGISTRY = "ghcr.io/webtech-network"
SOURCE = "https://github.com/webtech-network/autograder"  # links each package to this repository
IMAGES_DIR = Path(__file__).resolve().parents[1] / "sandbox_manager" / "images"
#: Same value as ``sandbox_manager.manager.RUNTIME_LANGUAGES_LABEL`` (this script needs no project imports).
LANGUAGES_LABEL = "autograder.runtime.languages"
_ABSENT = re.compile(r"no such manifest|manifest unknown|name unknown|not found|denied", re.IGNORECASE)
#: What a client without credentials is told for a reference it cannot pull.
_NOT_PULLABLE = re.compile(_ABSENT.pattern + "|unauthorized", re.IGNORECASE)
_LANGUAGES = re.compile(r'^LABEL\s+' + re.escape(LANGUAGES_LABEL) + r'="([^"]+)"', re.MULTILINE)


@dataclass(frozen=True)
class RuntimeImage:
    """One ``Dockerfile.<name>``, read once, and the languages its label declares."""
    name: str
    dockerfile: Path
    content: bytes
    languages: Tuple[str, ...]

    @property
    def ref(self) -> str:
        """The versioned reference hosts use: a new Dockerfile content is a new tag."""
        return f"{REGISTRY}/autograder-sandbox-{self.name}:{hashlib.sha256(self.content).hexdigest()[:12]}"


def catalog(directory: Path = IMAGES_DIR) -> List[RuntimeImage]:
    """Every runtime image defined in ``directory``, sorted by name."""
    images = []
    for dockerfile in sorted(directory.glob("Dockerfile.*")):
        content = dockerfile.read_bytes()
        match = _LANGUAGES.search(content.decode("utf-8"))
        if match is None:
            raise ValueError(f"{dockerfile} must declare LABEL {LANGUAGES_LABEL}=\"<language>[,...]\"")
        languages = tuple(item.strip() for item in match.group(1).split(","))
        images.append(RuntimeImage(dockerfile.suffix[1:], dockerfile, content, languages))
    return images


def select(names: Sequence[str]) -> List[RuntimeImage]:
    """The named images (all when ``names`` is empty); an unknown name is an error."""
    images = catalog()
    unknown = set(names) - {image.name for image in images}
    if unknown:
        raise SystemExit(f"unknown runtime image(s): {', '.join(sorted(unknown))}")
    return [image for image in images if not names or image.name in names]


def build(images: Sequence[RuntimeImage], *, no_cache: bool = False) -> None:
    """Build each image under its reference, with the Dockerfile on stdin and no context."""
    for image in images:
        args = ["docker", "build", "--tag", image.ref, "--label", f"org.opencontainers.image.source={SOURCE}"]
        if no_cache:
            args += ["--no-cache", "--pull"]
        print(f"Building {image.ref} ({', '.join(image.languages)})", flush=True)
        subprocess.run(args + ["-"], input=image.content, check=True)


def published(ref: str, env: Optional[Mapping[str, str]] = None) -> bool:
    """Whether the registry has ``ref``. An unexpected answer is an error, never "absent"."""
    # "denied" is how GHCR answers for a package that does not exist yet; a
    # token that truly lacks access is refused by the push that follows.
    return _served(ref, _ABSENT, env)


def anonymously_pullable(ref: str) -> bool:
    """Whether a client without credentials, such as a hosted runner, can pull ``ref``.

    GHCR tells such a client "unauthorized" for an existing private package and
    "denied" for one that does not exist; neither is pullable. Any other answer
    is an error, as in :func:`published`.
    """
    with tempfile.TemporaryDirectory() as anonymous:
        return _served(ref, _NOT_PULLABLE, {**os.environ, "DOCKER_CONFIG": anonymous})


def _served(ref: str, refusal: "re.Pattern[str]", env: Optional[Mapping[str, str]]) -> bool:
    found = subprocess.run(["docker", "manifest", "inspect", ref], capture_output=True, text=True, check=False,
                           env=env)
    if found.returncode == 0:
        return True
    if refusal.search(found.stderr):
        return False
    raise RuntimeError(f"cannot tell whether {ref} is published: {found.stderr.strip()}")


def publish(images: Sequence[RuntimeImage]) -> None:
    """Push the locally built references that the registry does not have yet."""
    for image in images:
        if published(image.ref):
            print(f"{image.ref} is already published; published references are immutable", flush=True)
            continue
        subprocess.run(["docker", "push", image.ref], check=True)


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Command line: ``list``, ``build [--no-cache]`` or ``publish``, optionally for some names."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["list", "build", "publish"])
    parser.add_argument("names", nargs="*", help="image names (Dockerfile suffixes); default: all")
    parser.add_argument("--no-cache", action="store_true", help="build from scratch, re-pulling the bases")
    args = parser.parse_args(argv)
    images = select(args.names)
    if args.command == "list":
        for image in images:
            for language in image.languages:
                print(f"{language}: {image.ref}")
    elif args.command == "build":
        build(images, no_cache=args.no_cache)
    else:
        publish(images)


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        sys.exit(exc.returncode)
