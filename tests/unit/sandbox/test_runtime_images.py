"""ENV-04: versioned runtime images, and a clear failure for a missing or mismatched one.

The image contents are checked against real Docker in
``tests/integration/test_runtime_images.py``.
"""
import re
import subprocess
from pathlib import Path

import docker
import pytest
import yaml

from autograder.models.language import Language
from sandbox_manager.errors import RuntimeImageError
from sandbox_manager.manager import RUNTIME_LANGUAGES_LABEL, SandboxManager
from sandbox_manager.models.pool_config import SandboxPoolConfig, runtime_images
from scripts import sandbox_images
from tests.sandbox_profiles import TEST_IMAGES
from tests.unit.sandbox.fakes import FakeDocker, owner, pool_config

ROOT = Path(__file__).resolve().parents[3]


# ----- the shipped profile names exactly the images this checkout builds ---------------

def test_shipped_profile_uses_the_versioned_images_built_from_this_checkout():
    built = {Language(language): image.ref for image in sandbox_images.catalog() for language in image.languages}
    shipped = runtime_images(yaml.safe_load((ROOT / "sandbox_config.yml").read_text())["runtimes"])
    assert shipped == built, "sandbox_config.yml is stale; run python scripts/sandbox_images.py list"


def test_every_language_has_exactly_one_runtime_image():
    languages = [language for image in sandbox_images.catalog() for language in image.languages]
    assert sorted(languages) == sorted(language.value for language in Language)


def test_tests_run_against_the_shipped_profile():
    shipped = runtime_images(yaml.safe_load((ROOT / "sandbox_config.yml").read_text())["runtimes"])
    assert TEST_IMAGES == shipped


def test_reference_is_derived_from_the_dockerfile_content(tmp_path):
    dockerfile = tmp_path / "Dockerfile.python"
    dockerfile.write_text('FROM scratch\nLABEL autograder.runtime.languages="python"\n')
    first = sandbox_images.catalog(tmp_path)
    assert [(image.name, image.languages) for image in first] == [("python", ("python",))]
    assert re.fullmatch(r"ghcr\.io/webtech-network/autograder-sandbox-python:[0-9a-f]{12}", first[0].ref)

    dockerfile.write_text(dockerfile.read_text() + "CMD [\"python3\"]\n")
    assert sandbox_images.catalog(tmp_path)[0].ref != first[0].ref  # a rebuild never reuses a tag


def test_build_script_and_host_read_the_same_label():
    assert sandbox_images.LANGUAGES_LABEL == RUNTIME_LANGUAGES_LABEL


def test_dockerfile_must_declare_its_languages(tmp_path):
    (tmp_path / "Dockerfile.python").write_text("FROM scratch\n")
    with pytest.raises(ValueError, match=RUNTIME_LANGUAGES_LABEL):
        sandbox_images.catalog(tmp_path)


@pytest.mark.parametrize("image", sandbox_images.catalog(), ids=lambda image: image.name)
def test_runtime_dockerfile_is_context_free_and_pins_a_base_by_digest(image):
    lines = [line.strip() for line in image.dockerfile.read_text().splitlines()]
    instructions = [line.split()[0].upper() for line in lines if line and not line.startswith("#")]
    assert "COPY" not in instructions and "ADD" not in instructions
    bases = [line.split()[1] for line in lines if line.upper().startswith("FROM ")]
    assert bases and all(re.fullmatch(r"[\w.\-/]+:[\w.\-]+@sha256:[0-9a-f]{64}", base) for base in bases)
    assert not any(":latest" in base for base in bases)


def test_images_are_built_without_a_build_context(monkeypatch):
    calls = []
    monkeypatch.setattr(subprocess, "run", lambda args, **kwargs: calls.append((args, kwargs)))
    image = sandbox_images.catalog()[0]
    sandbox_images.build([image])
    (args, kwargs), = calls
    assert args[-1] == "-" and args[args.index("--tag") + 1] == image.ref
    assert kwargs["input"] == image.dockerfile.read_bytes() and kwargs["check"] is True


class Registry:
    """The docker CLI at the registry boundary: ``manifest inspect`` answers, ``push`` is recorded."""

    def __init__(self, inspect_answer):
        self.inspect_answer = inspect_answer
        self.pushed = []

    def __call__(self, args, **kwargs):
        if args[:3] == ["docker", "manifest", "inspect"]:
            code, stderr = self.inspect_answer
            return subprocess.CompletedProcess(args, code, stdout="", stderr=stderr)
        assert args[:2] == ["docker", "push"] and kwargs["check"] is True
        self.pushed.append(args[2])
        return subprocess.CompletedProcess(args, 0)


@pytest.mark.parametrize("answer,pushed", [
    ((0, ""), False),                                                       # published: never overwritten
    ((1, "no such manifest: ghcr.io/x"), True),
    ((1, 'Get "https://ghcr.io/v2/x/manifests/abc": denied'), True),       # GHCR: package not created yet
])
def test_publish_pushes_only_references_the_registry_lacks(monkeypatch, answer, pushed):
    registry = Registry(answer)
    monkeypatch.setattr(subprocess, "run", registry)
    image = sandbox_images.catalog()[0]
    sandbox_images.publish([image])
    assert registry.pushed == ([image.ref] if pushed else [])


@pytest.mark.parametrize("stderr", ["unauthorized", "dial tcp: i/o timeout"])
def test_publish_stops_when_it_cannot_tell_whether_a_reference_exists(monkeypatch, stderr):
    registry = Registry((1, stderr))
    monkeypatch.setattr(subprocess, "run", registry)
    with pytest.raises(RuntimeError, match="cannot tell whether"):
        sandbox_images.publish(sandbox_images.catalog())
    assert registry.pushed == []


# ----- a host refuses to start with a missing or mismatched image ---------------------

def start(client, *configs):
    return SandboxManager(list(configs), client, runtime="runc", max_sandboxes=2, owner=owner(), reclaim_orphans=False, monitor_interval=60)


def test_missing_runtime_image_fails_at_startup_and_creates_nothing():
    client = FakeDocker()
    image = TEST_IMAGES[Language.PYTHON]
    client.images.missing.add(image)
    with pytest.raises(RuntimeImageError) as raised:
        start(client, pool_config(Language.PYTHON, pool_size=1))
    message = str(raised.value)
    assert image in message and "python" in message and f"docker pull {image}" in message
    assert client.containers.run_calls == [] and client.live == {}


@pytest.mark.parametrize("labels", [{}, {RUNTIME_LANGUAGES_LABEL: "cpp,c"}, {RUNTIME_LANGUAGES_LABEL: ""}],
                         ids=["unlabelled", "other-runtime", "empty"])
def test_image_that_does_not_declare_the_language_fails_at_startup(labels):
    client = FakeDocker()
    image = TEST_IMAGES[Language.PYTHON]
    client.images.labels[image] = labels
    with pytest.raises(RuntimeImageError, match=r"does not declare the 'python' runtime") as raised:
        start(client, pool_config(Language.JAVA), pool_config(Language.PYTHON, pool_size=1))
    assert image in str(raised.value)
    assert client.containers.run_calls == []


def test_one_image_may_serve_several_declared_languages():
    client = FakeDocker()
    client.images.labels[TEST_IMAGES[Language.CPP]] = {RUNTIME_LANGUAGES_LABEL: "cpp, c"}
    manager = start(client, pool_config(Language.CPP), pool_config(Language.C))
    try:
        assert set(manager.language_pools) == {Language.CPP, Language.C}
        assert client.images.get_calls == [TEST_IMAGES[Language.CPP]] * 2
    finally:
        manager.shutdown()


def test_docker_failure_while_checking_images_is_not_reported_as_a_missing_image():
    client = FakeDocker()

    def unreachable(reference):
        raise docker.errors.APIError("daemon unreachable")
    client.images.get = unreachable
    with pytest.raises(docker.errors.APIError):
        start(client, pool_config())


def test_startup_failure_closes_a_client_the_manager_created(monkeypatch):
    client = FakeDocker()
    client.images.missing.add(TEST_IMAGES[Language.PYTHON])
    monkeypatch.setattr(docker, "from_env", lambda: client)
    with pytest.raises(RuntimeImageError):
        SandboxManager([pool_config()], runtime="runc", max_sandboxes=2, owner=owner(), reclaim_orphans=False,
                       monitor_interval=60)
    client.close.assert_called_once()


def test_a_custom_image_needs_only_the_languages_label():
    client = FakeDocker()
    client.images.labels["registry.local/py:3.13"] = {RUNTIME_LANGUAGES_LABEL: "python"}
    config = SandboxPoolConfig(language=Language.PYTHON, image="registry.local/py:3.13", pool_size=0,
                               running_timeout=60)
    start(client, config).shutdown()
