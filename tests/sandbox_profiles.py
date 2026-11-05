"""Host runtime profiles used by tests that start a real sandbox host."""
import functools
import os
from pathlib import Path

import yaml

from sandbox_manager.docker_profile import GVISOR_RUNTIME, RUNC_RUNTIME, RUNTIMES
from sandbox_manager.models.pool_config import runtime_images

#: The shipped profile's images (``make sandbox-build-all`` builds them locally), so
#: tests run against exactly the runtimes hosts use.
TEST_IMAGES = runtime_images(yaml.safe_load(
    (Path(__file__).resolve().parents[1] / "sandbox_config.yml").read_text(encoding="utf-8"))["runtimes"])


@functools.cache
def offered_runtimes() -> tuple:
    """The OCI runtimes the local Docker daemon offers, gVisor first (Docker always offers runc)."""
    import docker  # pylint: disable=import-outside-toplevel
    client = docker.from_env()
    try:
        offered = client.info().get("Runtimes") or {}
    finally:
        client.close()
    return tuple(runtime for runtime in RUNTIMES if runtime == RUNC_RUNTIME or runtime in offered)


def suite_runtime() -> str:
    """The runtime Docker suites run under: ``AUTOGRADER_TEST_RUNTIME``, else gVisor when installed.

    Suites that pin a per-runtime guarantee parametrize over :func:`offered_runtimes` instead.
    """
    chosen = os.environ.get("AUTOGRADER_TEST_RUNTIME")
    if chosen:
        return chosen
    return GVISOR_RUNTIME if GVISOR_RUNTIME in offered_runtimes() else RUNC_RUNTIME



def sandbox_config(languages=tuple(TEST_IMAGES), pool_size=0, max_sandboxes=2, running_timeout=60, runtime=None):
    """A sandbox_config.yml text offering runtimes only for ``languages`` (``runtime``: see :func:`suite_runtime`)."""
    images = "".join(f"  {language.value}: {TEST_IMAGES[language]}\n" for language in languages)
    return (f"general:\n  runtime: {runtime or suite_runtime()}\n  max_sandboxes: {max_sandboxes}\n"
            f"  pool_size: {pool_size}\n  running_timeout: {running_timeout}\nruntimes:\n{images}")
